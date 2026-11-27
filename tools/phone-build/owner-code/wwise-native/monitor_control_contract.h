#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>

namespace wwise_diag {

// AK::Monitor::PostString receives the raw token; the callback reports the
// exact formatted Game Message text observed in the bounded R13 run.
static constexpr char kNativeControlPostedToken[] = "WwiseManagedNativeMonitorControl";
static constexpr char kNativeControlReportedMessage[] = "WwiseManagedNativeMonitorControl (Game Message)";

// Serializes only owner-thread phase transitions. DSP/LocalOutput callbacks
// never acquire this gate. Contenders fail immediately; they never wait.
struct PreInitTransition {
    std::atomic_flag owner_gate = ATOMIC_FLAG_INIT;
    std::atomic<uint32_t> engine_init_attempted{0};
    // Monotonic for the process lifetime; unlike capture_used, this is never
    // reset after a failed speaker query or failed RegisterCaptureCallback.
    std::atomic<uint32_t> capture_attempted{0};
};

inline bool TryAcquirePreInitTransition(PreInitTransition& state) {
    return !state.owner_gate.test_and_set(std::memory_order_acquire);
}

inline void ReleasePreInitTransition(PreInitTransition& state) {
    state.owner_gate.clear(std::memory_order_release);
}

class ScopedPreInitTransition {
public:
    explicit ScopedPreInitTransition(PreInitTransition& state)
        : state_(state), acquired_(TryAcquirePreInitTransition(state_)) {}
    ~ScopedPreInitTransition() {
        if (acquired_) ReleasePreInitTransition(state_);
    }
    ScopedPreInitTransition(const ScopedPreInitTransition&) = delete;
    ScopedPreInitTransition& operator=(const ScopedPreInitTransition&) = delete;
    bool acquired() const { return acquired_; }

private:
    PreInitTransition& state_;
    bool acquired_;
};

inline bool TryMarkEngineInitAttempted(PreInitTransition& state,
                                       const std::atomic<uint32_t>& monitor_armed) {
    if (!TryAcquirePreInitTransition(state)) return false;
    uint32_t expected = 0;
    const bool marked = monitor_armed.load(std::memory_order_acquire) == 1 &&
        state.engine_init_attempted.compare_exchange_strong(
            expected, 1, std::memory_order_acq_rel);
    ReleasePreInitTransition(state);
    return marked;
}

inline void MarkCaptureAttempted(PreInitTransition& state) {
    state.capture_attempted.store(1, std::memory_order_release);
}

template <typename CharT>
inline bool IsExactMonitorControlText(const CharT* message) {
    if (!message) return false;
    for (size_t i = 0; i < sizeof(kNativeControlReportedMessage) - 1; ++i) {
        if (message[i] != static_cast<CharT>(kNativeControlReportedMessage[i])) return false;
    }
    return message[sizeof(kNativeControlReportedMessage) - 1] == static_cast<CharT>(0);
}

template <typename CharT>
inline bool IsExactMonitorControlCallback(
    uint32_t code, uint32_t level, uint32_t playing_id, uint64_t game_object_id,
    const CharT* message, uint32_t expected_game_message_code,
    uint32_t expected_message_level, uint64_t invalid_game_object_id) {
    return code == expected_game_message_code &&
           level == expected_message_level && playing_id == 0 &&
           game_object_id == invalid_game_object_id &&
           IsExactMonitorControlText(message);
}

template <typename CharT>
inline void RecordControlMarkerIfExact(
    std::atomic<uint64_t>& counter, uint32_t code, uint32_t level,
    uint32_t playing_id, uint64_t game_object_id, const CharT* message,
    uint32_t expected_game_message_code, uint32_t expected_message_level,
    uint64_t invalid_game_object_id) {
    if (IsExactMonitorControlCallback(code, level, playing_id, game_object_id,
                                      message, expected_game_message_code,
                                      expected_message_level, invalid_game_object_id))
        counter.fetch_add(1, std::memory_order_relaxed);
}

inline bool CanDisarmBeforeInit(uint32_t armed, uint32_t init_attempted,
                               uint32_t capture_attempted, uint32_t capture_registered,
                               bool native_initialized) {
    return armed == 1 && init_attempted == 0 && capture_attempted == 0 &&
           capture_registered == 0 && !native_initialized;
}

}  // namespace wwise_diag
