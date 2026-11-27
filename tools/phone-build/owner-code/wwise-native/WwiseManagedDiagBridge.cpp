// Authored single-library extension draft. Root must integrate/review before use.
#include <AK/SoundEngine/Common/AkSoundEngine.h>
#include <AK/Tools/Common/AkMonitorError.h>
#include <atomic>
#include <cstdint>
#include <limits>
#include <type_traits>
#include "monitor_capture_core.h"
#include "PcmReadbackRingV1.hpp"

static_assert(std::is_same<AkOutputDeviceID, AkUInt64>::value,
              "Wwise output-device identity type changed; review bridge ABI");
static_assert(sizeof(AkOutputDeviceID) == sizeof(uint64_t) && sizeof(AkOutputDeviceID) == 8,
              "Wwise output-device identity must remain 64-bit");
static_assert(std::is_unsigned<AkOutputDeviceID>::value,
              "Wwise output-device identity must remain unsigned");

namespace wwise_diag {
static_assert(ATOMIC_LLONG_LOCK_FREE == 2,
              "Diagnostic counters require lock-free 64-bit atomics on ARM64");
struct State : Counters {
    PreInitTransition preinit;
    std::atomic<uint32_t> monitor_armed{0};
    std::atomic<uint32_t> monitor_control_post_attempted{0};
    std::atomic<uint32_t> managed_monitor_level{0};
    std::atomic<uint32_t> engine_term_returned{0};
    std::atomic<uint32_t> callback_manager_term_returned{0};
    std::atomic<uint32_t> capture_registered{0};
    std::atomic<uint32_t> capture_used{0};
    std::atomic<uint32_t> capture_selector_mode{0};
    std::atomic<uint64_t> capture_selector_id{0};
    std::atomic<uint32_t> capture_sample_rate{0};
    std::atomic<uint64_t> capture_generation{0};
    ror2lab_audio_diag::PcmReadbackRingV1 readback;
    std::atomic<int32_t> monitor_install_result{AK_NotInitialized};
    std::atomic<int32_t> monitor_disarm_result{AK_NotInitialized};
    std::atomic<int32_t> capture_register_result{AK_NotInitialized};
    std::atomic<int32_t> capture_unregister_result{AK_NotInitialized};
};
static State g;
}

namespace AkCallbackSerializerHelper {
void LocalOutput(AK::Monitor::ErrorCode, const AkOSChar*, AK::Monitor::ErrorLevel,
                 AkPlayingID, AkGameObjectID);
}

namespace {
constexpr int32_t kBridgeBusy = -32101;
constexpr int32_t kBridgeNotTermed = -32102;
constexpr int32_t kBridgeCallbackManagerNotTermed = -32104;
constexpr int32_t kBridgeCaptureNotReady = -32103;
constexpr int32_t kBridgeInitAlreadyEntered = -32105;
constexpr int32_t kBridgeEngineAlreadyInitialized = -32106;
constexpr int32_t kBridgeCaptureAttemptedBeforeInitDisarm = -32107;
constexpr int32_t kBridgeControlOutOfPhase = -32108;
constexpr int32_t kBridgeControlAlreadyPosted = -32109;
constexpr int32_t kBridgeCaptureSelectorInvalid = -32110;
constexpr uint32_t kCaptureSelectorMainOutput = 0;
constexpr uint32_t kCaptureSelectorSpecificOutput = 1;
constexpr uint32_t kErrorMask = AK::Monitor::ErrorLevel_Error;
constexpr uint32_t kWarningMask = AK::Monitor::ErrorLevel_Message;
AK::Monitor::LocalOutputFunc SerializerLocalOutput =
    &AkCallbackSerializerHelper::LocalOutput;

void CaptureCallback(AkAudioBuffer& buffer, AkOutputDeviceID output, void* cookie) {
    if (cookie != &wwise_diag::g) return;
    wwise_diag::g.capture_callbacks.fetch_add(1, std::memory_order_relaxed);
    wwise_diag::RecordCaptureOutputID(wwise_diag::g, output);
    const uint32_t channels = buffer.NumChannels();
    const uint32_t frames = buffer.uValidFrames;
    const AkChannelConfig channel_config = buffer.GetChannelConfig();
    const uint32_t channel_mask = channel_config.uChannelMask;
    wwise_diag::g.capture_frames.fetch_add(frames, std::memory_order_relaxed);
    const uint64_t available = static_cast<uint64_t>(frames) * channels;
    const uint64_t already_analyzed =
        wwise_diag::g.sample_count.load(std::memory_order_relaxed);
    const uint32_t count = wwise_diag::BoundedSampleCount(frames, channels, already_analyzed);
    const float* interleaved = static_cast<const float*>(buffer.GetInterleavedData());
    const uint32_t sample_rate =
        wwise_diag::g.capture_sample_rate.load(std::memory_order_acquire);
    if (!channels || channels > 16 || frames > buffer.MaxFrames() ||
        available >
            wwise_diag::kMaxSamplesPerCallback ||
        (frames && !interleaved)) {
        wwise_diag::g.rejected_buffers.fetch_add(1, std::memory_order_relaxed);
        wwise_diag::g.readback.Observe(nullptr, 0, sample_rate, channels,
            channel_mask, output, false);
        return;
    }
    if (count < available)
        wwise_diag::g.capped_buffers.fetch_add(1, std::memory_order_relaxed);
    const bool windowEndedAtSampleBound = count < available &&
        already_analyzed + count == wwise_diag::kMaxCaptureSamples;
    wwise_diag::g.readback.Observe(interleaved, count, sample_rate, channels,
        channel_mask, output, count == available || windowEndedAtSampleBound);
    wwise_diag::CountPcm(
        wwise_diag::g, interleaved, count);
}
}

extern "C" {
#if defined(__GNUC__)
#define WWISE_DIAG_EXPORT __attribute__((visibility("default")))
#else
#define WWISE_DIAG_EXPORT
#endif

// Call before the owner invokes AkSoundEngine.Init. This bridge only registers
// the official local-output callback; it never creates or terminates Wwise.
WWISE_DIAG_EXPORT int32_t WwiseDiag_MonitorArm() {
    uint32_t expected = 0;
    if (!wwise_diag::g.monitor_armed.compare_exchange_strong(
            expected, 2, std::memory_order_acq_rel)) return kBridgeBusy;
    const AKRESULT result = AK::Monitor::SetLocalOutput(
        AK::Monitor::ErrorLevel_All, SerializerLocalOutput);
    wwise_diag::g.monitor_install_result.store(static_cast<int32_t>(result),
                                                std::memory_order_release);
    if (result != AK_Success) {
        wwise_diag::g.monitor_armed.store(0, std::memory_order_release);
        return static_cast<int32_t>(result);
    }
    wwise_diag::g.monitor_armed.store(1, std::memory_order_release);
    return static_cast<int32_t>(result);
}

// Called as the first operation inside AkCallbackSerializerHelper::LocalOutput,
// before its existing IsInitialized guard. Counts callbacks and correlates the
// exact authored control marker without allocation or serializer access.
WWISE_DIAG_EXPORT void WwiseDiag_RecordMonitor(uint32_t code, uint32_t level,
                                            uint32_t playing_id,
                                            uint64_t game_object_id,
                                            const AkOSChar* message) {
    if (wwise_diag::g.monitor_armed.load(std::memory_order_acquire) != 1) return;
    wwise_diag::CountMonitor(
        wwise_diag::g, code, level, playing_id, game_object_id, message,
        kErrorMask, kWarningMask,
        static_cast<uint32_t>(AK::Monitor::ErrorCode_GameMessage),
        static_cast<uint32_t>(AK::Monitor::ErrorLevel_Message),
        static_cast<uint64_t>(AK_INVALID_GAME_OBJECT));
}

// The owner calls this exactly once immediately before invoking official Init.
// It prevents an ambiguous Init attempt from using the pre-Init disarm path,
// even if a fresh IsInitialized query later reports false.
WWISE_DIAG_EXPORT int32_t WwiseDiag_MarkEngineInitAttempted() {
    return wwise_diag::TryMarkEngineInitAttempted(
               wwise_diag::g.preinit,
               wwise_diag::g.monitor_armed)
        ? AK_Success
        : kBridgeBusy;
}

WWISE_DIAG_EXPORT int32_t WwiseDiag_MonitorIsArmed() {
    return wwise_diag::g.monitor_armed.load(std::memory_order_acquire) == 1;
}

void WwiseDiag_SetManagedMonitorLevel(uint32_t level) {
    wwise_diag::g.managed_monitor_level.store(level, std::memory_order_release);
}

int32_t WwiseDiag_ShouldSerializeMonitor(uint32_t level) {
    if (!WwiseDiag_MonitorIsArmed()) return 1;
    return (wwise_diag::g.managed_monitor_level.load(std::memory_order_acquire) & level) != 0;
}

// Unique native control marker used only after successful Init. The callback
// counter is correlated by exact message content in LocalOutput.
WWISE_DIAG_EXPORT int32_t WwiseDiag_PostMonitorControl() {
    if (!WwiseDiag_MonitorIsArmed()) return kBridgeBusy;
    if (wwise_diag::g.preinit.engine_init_attempted.load(std::memory_order_acquire) != 1 ||
        !AK::SoundEngine::IsInitialized() ||
        wwise_diag::g.engine_term_returned.load(std::memory_order_acquire) != 0 ||
        wwise_diag::g.callback_manager_term_returned.load(std::memory_order_acquire) != 0)
        return kBridgeControlOutOfPhase;
    uint32_t expected = 0;
    if (!wwise_diag::g.monitor_control_post_attempted.compare_exchange_strong(
            expected, 1, std::memory_order_acq_rel)) return kBridgeControlAlreadyPosted;
    return static_cast<int32_t>(AK::Monitor::PostString(
        wwise_diag::kNativeControlPostedToken, AK::Monitor::ErrorLevel_Message));
}

WWISE_DIAG_EXPORT void WwiseDiag_EngineTermReturned() {
    wwise_diag::g.engine_term_returned.store(1, std::memory_order_release);
}

WWISE_DIAG_EXPORT void WwiseDiag_CallbackManagerTermReturned() {
    wwise_diag::g.callback_manager_term_returned.store(1, std::memory_order_release);
}

WWISE_DIAG_EXPORT int32_t WwiseDiag_MonitorDisarmAfterTerm() {
    if (!wwise_diag::g.engine_term_returned.load(std::memory_order_acquire))
        return kBridgeNotTermed;
    if (!wwise_diag::g.callback_manager_term_returned.load(std::memory_order_acquire))
        return kBridgeCallbackManagerNotTermed;
    if (wwise_diag::g.capture_registered.load(std::memory_order_acquire) != 0)
        return kBridgeCaptureNotReady;
    const AKRESULT result = AK::Monitor::SetLocalOutput(0, nullptr);
    wwise_diag::g.monitor_disarm_result.store(static_cast<int32_t>(result),
                                               std::memory_order_release);
    if (result == AK_Success) {
        // Release the optional bounded waveform buffer only after both native
        // Term-return markers and the existing callback-absent gate above.
        // A rare outstanding callback leaves the 1 MiB allocation retained;
        // cleanup never spins or blocks an audio thread to free it.
        wwise_diag::g.readback.ReleaseAfterEngineAndCallbackTerms();
        wwise_diag::g.monitor_armed.store(3, std::memory_order_release);
    }
    return static_cast<int32_t>(result);
}

// Cleanup for a registered monitor when official Init was never entered.
// Native Init-attempt, capture ownership, and a fresh native state query must
// all permit release; no engine/callback-manager Term markers are fabricated.
WWISE_DIAG_EXPORT int32_t WwiseDiag_MonitorDisarmBeforeInit() {
    // Hold the owner-only transition gate across the state query and detach so
    // MarkEngineInitAttempted cannot pass between the check and SetLocalOutput.
    // Callbacks do not acquire this gate; contention returns immediately.
    wwise_diag::ScopedPreInitTransition transition(wwise_diag::g.preinit);
    if (!transition.acquired()) return kBridgeBusy;
    if (wwise_diag::g.monitor_armed.load(std::memory_order_acquire) != 1)
        return kBridgeBusy;
    if (wwise_diag::g.preinit.engine_init_attempted.load(std::memory_order_acquire) != 0)
        return kBridgeInitAlreadyEntered;
    const uint32_t capture_used = wwise_diag::g.capture_used.load(std::memory_order_acquire);
    const uint32_t capture_attempted = wwise_diag::g.preinit.capture_attempted.load(
        std::memory_order_acquire);
    const uint32_t capture_registered = wwise_diag::g.capture_registered.load(std::memory_order_acquire);
    const bool native_initialized = AK::SoundEngine::IsInitialized();
    if (capture_attempted != 0 || capture_used != 0 || capture_registered != 0)
        return kBridgeCaptureAttemptedBeforeInitDisarm;
    if (native_initialized) return kBridgeEngineAlreadyInitialized;
    if (!wwise_diag::CanDisarmBeforeInit(
            wwise_diag::g.monitor_armed.load(std::memory_order_acquire),
            wwise_diag::g.preinit.engine_init_attempted.load(std::memory_order_acquire),
            capture_attempted, capture_registered, native_initialized))
        return kBridgeBusy;

    const AKRESULT result = AK::Monitor::SetLocalOutput(0, nullptr);
    wwise_diag::g.monitor_disarm_result.store(static_cast<int32_t>(result),
                                               std::memory_order_release);
    if (result == AK_Success)
        wwise_diag::g.monitor_armed.store(3, std::memory_order_release);
    return static_cast<int32_t>(result);
}

// Register only after engine Init and a fresh valid main-output query. The
// SDK invalid-output selector (AK_INVALID_OUTPUT_DEVICE_ID) requests the main
// output; the callback reports its actual opaque AkOutputDeviceID. Preserve
// that callback value, including zero, without comparing it to the selector.
WWISE_DIAG_EXPORT int32_t WwiseDiag_CaptureRegister(uint32_t selector_mode,
                                                     uint64_t output_selector) {
    if ((selector_mode == kCaptureSelectorMainOutput && output_selector != 0) ||
        (selector_mode == kCaptureSelectorSpecificOutput &&
            (output_selector == 0 || output_selector == std::numeric_limits<uint64_t>::max())) ||
        (selector_mode != kCaptureSelectorMainOutput &&
            selector_mode != kCaptureSelectorSpecificOutput))
        return kBridgeCaptureSelectorInvalid;
    // Mark the attempt monotonically before any validation or SDK call. A
    // failed query/register still makes pre-Init disarm ineligible.
    wwise_diag::ScopedPreInitTransition transition(wwise_diag::g.preinit);
    if (!transition.acquired()) return kBridgeBusy;
    wwise_diag::MarkCaptureAttempted(wwise_diag::g.preinit);
    uint32_t unused = 0;
    if (!wwise_diag::g.capture_used.compare_exchange_strong(
            unused, 1, std::memory_order_acq_rel) ||
        wwise_diag::g.capture_registered.load(std::memory_order_acquire))
        return kBridgeBusy;
    // Keep the existing default/main readiness check byte-for-byte in meaning.
    // For a specific source-owned output, don't incorrectly gate registration
    // on the unrelated main-output configuration; the SDK registration result
    // is the authoritative selected-output admission result.
    if (selector_mode == kCaptureSelectorMainOutput) {
        const AkChannelConfig output = AK::SoundEngine::GetSpeakerConfiguration(0);
        if (!output.IsValid() || output.uNumChannels == 0) {
            wwise_diag::g.capture_used.store(0, std::memory_order_release);
            return kBridgeCaptureNotReady;
        }
    }
    const AkUInt32 sample_rate = AK::SoundEngine::GetSampleRate();
    const uint64_t generation =
        wwise_diag::g.capture_generation.fetch_add(1, std::memory_order_acq_rel) + 1;
    const bool expected_output_known = selector_mode == kCaptureSelectorSpecificOutput;
    if (!wwise_diag::g.readback.Initialize(generation, expected_output_known,
            output_selector, sample_rate) || !wwise_diag::g.readback.Begin()) {
        wwise_diag::g.capture_used.store(0, std::memory_order_release);
        return kBridgeCaptureNotReady;
    }
    wwise_diag::g.capture_sample_rate.store(sample_rate, std::memory_order_release);
    const AkOutputDeviceID requested_output = selector_mode == kCaptureSelectorMainOutput
        ? static_cast<AkOutputDeviceID>(AK_INVALID_OUTPUT_DEVICE_ID)
        : static_cast<AkOutputDeviceID>(output_selector);
    wwise_diag::g.capture_selector_mode.store(selector_mode, std::memory_order_release);
    wwise_diag::g.capture_selector_id.store(output_selector, std::memory_order_release);
    const AKRESULT result = AK::SoundEngine::RegisterCaptureCallback(
        &CaptureCallback, requested_output, &wwise_diag::g);
    wwise_diag::g.capture_register_result.store(static_cast<int32_t>(result),
                                                 std::memory_order_release);
    if (result == AK_Success)
        wwise_diag::g.capture_registered.store(1, std::memory_order_release);
    else {
        // The existing lease treats this AK failure as no callback ownership.
        // Keep storage allocated for process lifetime, but make its sample
        // result unexportable in case the native call boundary was ambiguous.
        wwise_diag::g.readback.InvalidateBeforeSuccessfulRegistration();
        wwise_diag::g.capture_used.store(0, std::memory_order_release);
        wwise_diag::g.capture_selector_mode.store(0, std::memory_order_release);
        wwise_diag::g.capture_selector_id.store(0, std::memory_order_release);
    }
    return static_cast<int32_t>(result);
}

// New fixed-width readback ABI. ReadMetadata seals only after the exact AK
// unregister result and native absent-registration marker are both present.
// A Busy result means a callback already in flight is still leaving the ring;
// managed code may poll this metadata call a small bounded number of times.
WWISE_DIAG_EXPORT int32_t WwiseDiag_CaptureReadbackV1(uint32_t* words,
                                                       uint32_t capacity_words) {
    if (wwise_diag::g.capture_used.load(std::memory_order_acquire) != 1 ||
        wwise_diag::g.capture_register_result.load(std::memory_order_acquire) != AK_Success ||
        wwise_diag::g.capture_unregister_result.load(std::memory_order_acquire) != AK_Success ||
        wwise_diag::g.capture_registered.load(std::memory_order_acquire) != 0 ||
        wwise_diag::g.engine_term_returned.load(std::memory_order_acquire) != 0 ||
        wwise_diag::g.callback_manager_term_returned.load(std::memory_order_acquire) != 0)
        return kBridgeCaptureNotReady;
    const auto sealed = wwise_diag::g.readback.SealAfterSuccessfulUnregister();
    if (sealed != ror2lab_audio_diag::PcmReadbackRingV1::kOk)
        return static_cast<int32_t>(sealed);
    return static_cast<int32_t>(wwise_diag::g.readback.ReadMetadata(words, capacity_words));
}

WWISE_DIAG_EXPORT int32_t WwiseDiag_CaptureCopyV1(uint64_t generation,
    uint64_t expected_output_id, float* destination, uint32_t capacity_samples,
    uint32_t* copied_samples) {
    if (wwise_diag::g.capture_used.load(std::memory_order_acquire) != 1 ||
        wwise_diag::g.capture_register_result.load(std::memory_order_acquire) != AK_Success ||
        wwise_diag::g.capture_unregister_result.load(std::memory_order_acquire) != AK_Success ||
        wwise_diag::g.capture_registered.load(std::memory_order_acquire) != 0 ||
        wwise_diag::g.engine_term_returned.load(std::memory_order_acquire) != 0 ||
        wwise_diag::g.callback_manager_term_returned.load(std::memory_order_acquire) != 0)
        return kBridgeCaptureNotReady;
    const auto sealed = wwise_diag::g.readback.SealAfterSuccessfulUnregister();
    if (sealed != ror2lab_audio_diag::PcmReadbackRingV1::kOk)
        return static_cast<int32_t>(sealed);
    return static_cast<int32_t>(wwise_diag::g.readback.CopySamples(
        generation, expected_output_id, destination, capacity_samples, copied_samples));
}

// Caller invokes exactly once for a successful register. Failure preserves the
// registered bit so owner teardown must refuse Term and retain recovery state.
WWISE_DIAG_EXPORT int32_t WwiseDiag_CaptureUnregister(uint32_t selector_mode,
                                                       uint64_t output_selector) {
    if (!wwise_diag::g.capture_registered.load(std::memory_order_acquire))
        return kBridgeBusy;
    const uint32_t registered_mode = wwise_diag::g.capture_selector_mode.load(std::memory_order_acquire);
    const uint64_t registered_id = wwise_diag::g.capture_selector_id.load(std::memory_order_acquire);
    if (selector_mode != registered_mode || output_selector != registered_id)
        return kBridgeCaptureSelectorInvalid;
    const AkOutputDeviceID registered_output = registered_mode == kCaptureSelectorMainOutput
        ? static_cast<AkOutputDeviceID>(AK_INVALID_OUTPUT_DEVICE_ID)
        : static_cast<AkOutputDeviceID>(registered_id);
    const AKRESULT result = AK::SoundEngine::UnregisterCaptureCallback(
        &CaptureCallback, registered_output, &wwise_diag::g);
    wwise_diag::g.capture_unregister_result.store(static_cast<int32_t>(result),
                                                   std::memory_order_release);
    if (result == AK_Success) {
        wwise_diag::g.capture_registered.store(0, std::memory_order_release);
        wwise_diag::g.capture_selector_mode.store(0, std::memory_order_release);
        wwise_diag::g.capture_selector_id.store(0, std::memory_order_release);
    }
    return static_cast<int32_t>(result);
}

WWISE_DIAG_EXPORT void WwiseDiag_Snapshot(uint64_t* output, uint32_t capacity) {
    // R9: 23 data slots plus the schema discriminator in preserved slot 21.
    if (!wwise_diag::SnapshotBufferReady(output, capacity)) return;
    output[0] = wwise_diag::g.callbacks.load(std::memory_order_acquire);
    output[1] = wwise_diag::g.errors.load(std::memory_order_acquire);
    output[2] = wwise_diag::g.warnings.load(std::memory_order_acquire);
    output[3] = wwise_diag::g.capture_callbacks.load(std::memory_order_acquire);
    output[4] = wwise_diag::g.capture_frames.load(std::memory_order_acquire);
    output[5] = wwise_diag::g.sample_count.load(std::memory_order_acquire);
    output[6] = wwise_diag::g.finite_samples.load(std::memory_order_acquire);
    output[7] = wwise_diag::g.nonzero_finite_samples.load(std::memory_order_acquire);
    output[8] = wwise_diag::g.nonfinite_samples.load(std::memory_order_acquire);
    output[9] = wwise_diag::g.rejected_buffers.load(std::memory_order_acquire);
    output[10] = wwise_diag::g.capped_buffers.load(std::memory_order_acquire);
    output[11] = wwise_diag::g.capture_registered.load(std::memory_order_acquire);
    output[12] = wwise_diag::g.engine_term_returned.load(std::memory_order_acquire);
    output[13] = wwise_diag::g.monitor_armed.load(std::memory_order_acquire);
    output[14] = static_cast<uint64_t>(static_cast<int64_t>(
        wwise_diag::g.monitor_install_result.load(std::memory_order_acquire)));
    output[15] = static_cast<uint64_t>(static_cast<int64_t>(
        wwise_diag::g.capture_register_result.load(std::memory_order_acquire)));
    output[16] = static_cast<uint64_t>(static_cast<int64_t>(
        wwise_diag::g.capture_unregister_result.load(std::memory_order_acquire)));
    output[17] = wwise_diag::g.capture_used.load(std::memory_order_acquire);
    output[19] = static_cast<uint64_t>(static_cast<int64_t>(
        wwise_diag::g.monitor_disarm_result.load(std::memory_order_acquire)));
    output[20] = wwise_diag::g.callback_manager_term_returned.load(std::memory_order_acquire);
    output[23] = wwise_diag::g.preinit.engine_init_attempted.load(std::memory_order_acquire);
    wwise_diag::WriteCaptureIdentitySnapshot(output, wwise_diag::g);
}
}
