#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <AK/SoundEngine/Common/AkTypes.h>
#include "monitor_control_contract.h"

namespace wwise_diag {

// Fixed-size callback statistics: no strings, allocation, locks, or logging.
struct Counters {
    std::atomic<uint64_t> callbacks{0};
    std::atomic<uint64_t> errors{0};
    std::atomic<uint64_t> warnings{0};
    std::atomic<uint64_t> monitor_control_callbacks{0};
    std::atomic<uint64_t> capture_callbacks{0};
    std::atomic<uint64_t> capture_frames{0};
    std::atomic<AkOutputDeviceID> capture_output_id{AK_INVALID_OUTPUT_DEVICE_ID};
    std::atomic<uint64_t> sample_count{0};
    std::atomic<uint64_t> finite_samples{0};
    std::atomic<uint64_t> nonzero_finite_samples{0};
    std::atomic<uint64_t> nonfinite_samples{0};
    std::atomic<uint64_t> rejected_buffers{0};
    std::atomic<uint64_t> capped_buffers{0};
};

constexpr uint64_t kMaxCaptureSamples = 1'048'576;
constexpr uint32_t kMaxSamplesPerCallback = 8'192;
constexpr uint64_t kSnapshotSchemaVersion = 3;
constexpr uint32_t kSnapshotSlotCount = 24;

inline void RecordCaptureOutputID(Counters& c, AkOutputDeviceID output_id) {
    c.capture_output_id.store(output_id, std::memory_order_relaxed);
}

inline AkOutputDeviceID ReadCaptureOutputID(const Counters& c) {
    return c.capture_output_id.load(std::memory_order_acquire);
}

inline uint64_t CaptureOutputIDSnapshotValue(const Counters& c) {
    return static_cast<uint64_t>(ReadCaptureOutputID(c));
}

inline bool SnapshotBufferReady(uint64_t* output, uint32_t capacity) {
    return output != nullptr && capacity >= kSnapshotSlotCount;
}

inline void WriteCaptureIdentitySnapshot(uint64_t* output, const Counters& c) {
    output[18] = CaptureOutputIDSnapshotValue(c);
    output[21] = kSnapshotSchemaVersion;
    output[22] = c.monitor_control_callbacks.load(std::memory_order_acquire);
}

inline uint32_t BoundedSampleCount(uint32_t frames, uint32_t channels,
                                   uint64_t already_analyzed) {
    if (!channels || channels > 16 || already_analyzed >= kMaxCaptureSamples)
        return 0;
    const uint64_t remaining = kMaxCaptureSamples - already_analyzed;
    const uint64_t available = static_cast<uint64_t>(frames) * channels;
    const uint64_t bounded = available < kMaxSamplesPerCallback
                                 ? available
                                 : kMaxSamplesPerCallback;
    const uint64_t capped = bounded < remaining ? bounded : remaining;
    return static_cast<uint32_t>(capped);
}

template <typename CharT>
inline void CountMonitor(Counters& c, uint32_t code, uint32_t level,
                         uint32_t playing_id, uint64_t game_object_id,
                         const CharT* message, uint32_t error_bit,
                         uint32_t warning_bit, uint32_t game_message_code,
                         uint32_t message_level, uint64_t invalid_game_object_id) {
    c.callbacks.fetch_add(1, std::memory_order_relaxed);
    if (level & error_bit) c.errors.fetch_add(1, std::memory_order_relaxed);
    if (level & warning_bit) c.warnings.fetch_add(1, std::memory_order_relaxed);
    RecordControlMarkerIfExact(c.monitor_control_callbacks, code, level,
                                playing_id, game_object_id, message,
                                game_message_code, message_level,
                                invalid_game_object_id);
}

inline void CountPcm(Counters& c, const float* data, uint32_t count) {
    if (!data && count) {
        c.rejected_buffers.fetch_add(1, std::memory_order_relaxed);
        return;
    }
    uint64_t finite = 0, nonzero = 0, nonfinite = 0;
    for (uint32_t i = 0; i < count; ++i) {
        if (!std::isfinite(data[i])) {
            ++nonfinite;
        } else {
            ++finite;
            if (data[i] != 0.0f) ++nonzero;
        }
    }
    c.sample_count.fetch_add(count, std::memory_order_relaxed);
    c.finite_samples.fetch_add(finite, std::memory_order_relaxed);
    c.nonzero_finite_samples.fetch_add(nonzero, std::memory_order_relaxed);
    c.nonfinite_samples.fetch_add(nonfinite, std::memory_order_relaxed);
}

}  // namespace wwise_diag
