#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>

namespace ror2lab_audio_diag {

// Authored, SDK-independent bounded readback state. The production native
// owner would allocate this object before RegisterCapture and call Observe()
// from its existing callback. No Wwise or game implementation is reproduced.
class PcmReadbackRingV1 final {
public:
    static constexpr uint32_t kSchema = 1;
    static constexpr uint32_t kMetadataWords = 24;
    static constexpr uint32_t kMaxSamples = 262144;
    // Hard upper bound on work for any single callback invocation. The
    // current bridge's existing per-callback scan bound is 8,192 samples.
    static constexpr uint32_t kMaxCallbackSamples = 8192;
    static constexpr uint32_t kMaxObservedSamples = 1048576;
    static constexpr uint32_t kMaxChannels = 2;
    static constexpr uint32_t kFloat32Format = 1;

    enum Status : int32_t {
        kOk = 1,
        kInvalidArgument = -1,
        kNotReady = -2,
        kWrongGeneration = -3,
        kWrongOutput = -4,
        kCapacityMismatch = -5,
        kAlreadyCopied = -6,
        kInvalidWaveform = -7,
        kBusy = -8
    };

    PcmReadbackRingV1() noexcept;
    ~PcmReadbackRingV1();
    PcmReadbackRingV1(const PcmReadbackRingV1&) = delete;
    PcmReadbackRingV1& operator=(const PcmReadbackRingV1&) = delete;

    // Called off callback-thread before callback registration. Allocation
    // failure refuses registration; no allocation occurs in Observe().
    bool Initialize(uint64_t generation, bool expectedOutputKnown,
        uint64_t expectedOutputId, uint32_t engineSampleRate) noexcept;
    bool Begin() noexcept;
    void InvalidateBeforeSuccessfulRegistration() noexcept;
    bool ReleaseAfterEngineAndCallbackTerms() noexcept;

    // Feed exact interleaved float32 samples from the already-selected output
    // callback. The caller must use the pinned SDK's validated buffer access.
    void Observe(const float* samples, uint32_t sampleCount,
        uint32_t engineSampleRate, uint32_t channels, uint32_t channelMask,
        uint64_t callbackOutputId, bool completeBuffer = true) noexcept;

    // Only call after AK reports success unregistering the exact callback.
    // May return kBusy while a callback is completing; retry is outside the
    // callback and does not register or unregister anything.
    Status SealAfterSuccessfulUnregister() noexcept;

    // Metadata/readback are only available after a successful seal. Metadata
    // is a fixed-width word array to avoid cross-ABI struct packing.
    Status ReadMetadata(uint32_t* words, uint32_t capacityWords) const noexcept;
    Status CopySamples(uint64_t expectedGeneration, uint64_t expectedOutputId,
        float* destination, uint32_t capacitySamples,
        uint32_t* copiedSamples) noexcept;

private:
    static constexpr uint32_t kFlagOutputKnown = 1u << 0;
    static constexpr uint32_t kFlagFormatKnown = 1u << 1;
    static constexpr uint32_t kFlagTruncated = 1u << 2;
    static constexpr uint32_t kFlagWaveformValid = 1u << 3;
    static constexpr uint32_t kFlagOutputMismatch = 1u << 4;
    static constexpr uint32_t kFlagConcurrentCallback = 1u << 5;
    static constexpr uint32_t kFlagFormatChanged = 1u << 6;
    static constexpr uint32_t kFlagCounterOverflow = 1u << 7;
    static constexpr uint32_t kFlagChannelMaskKnown = 1u << 8;

    void SetCounterOverflow() noexcept;
    bool IsWaveformValid() const noexcept;

    float* samples_;
    uint64_t generation_;
    bool expectedOutputKnown_;
    uint64_t expectedOutputId_;
    uint64_t observedOutputId_;
    uint32_t sampleRate_;
    uint32_t channels_;
    uint32_t channelMask_;
    uint64_t totalSamples_;
    uint64_t finiteSamples_;
    uint64_t nonzeroFiniteSamples_;
    uint64_t nonfiniteSamples_;
    uint64_t callbacks_;
    uint32_t storedSamples_;
    double sumSquares_;
    float peakAbs_;
    float storedPeakAbs_;
    bool initialized_;
    std::atomic<bool> active_;
    bool sealRequested_;
    bool sealed_;
    bool copyAttempted_;
    bool outputKnown_;
    bool outputMismatch_;
    std::atomic<bool> concurrentCallback_;
    bool formatChanged_;
    bool counterOverflow_;
    std::atomic_flag callbackInFlight_ = ATOMIC_FLAG_INIT;
};

} // namespace ror2lab_audio_diag
