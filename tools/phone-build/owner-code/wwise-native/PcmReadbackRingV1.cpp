#include "PcmReadbackRingV1.h"

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <limits>

namespace ror2lab_audio_diag {

PcmReadbackRingV1::PcmReadbackRingV1() noexcept
    : samples_(nullptr), generation_(0), expectedOutputKnown_(false), expectedOutputId_(0),
      observedOutputId_(0), sampleRate_(0),
      channels_(0), channelMask_(0), totalSamples_(0), finiteSamples_(0),
      nonzeroFiniteSamples_(0), nonfiniteSamples_(0), callbacks_(0),
      storedSamples_(0), sumSquares_(0.0), peakAbs_(0.0f),
      storedPeakAbs_(0.0f), initialized_(false),
      active_(false), sealRequested_(false), sealed_(false), copyAttempted_(false),
      outputKnown_(false), outputMismatch_(false), concurrentCallback_(false), formatChanged_(false),
      counterOverflow_(false) {}

PcmReadbackRingV1::~PcmReadbackRingV1() {
    std::free(samples_);
    samples_ = nullptr;
}

bool PcmReadbackRingV1::Initialize(uint64_t generation, bool expectedOutputKnown,
    uint64_t expectedOutputId, uint32_t engineSampleRate) noexcept {
    if (initialized_ || generation == 0 || engineSampleRate == 0 ||
        (expectedOutputKnown && (expectedOutputId == 0 || expectedOutputId == std::numeric_limits<uint64_t>::max())))
        return false;
    const size_t bytes = static_cast<size_t>(kMaxSamples) * sizeof(float);
    samples_ = static_cast<float*>(std::malloc(bytes));
    if (samples_ == nullptr) return false;
    std::memset(samples_, 0, bytes);
    generation_ = generation;
    expectedOutputKnown_ = expectedOutputKnown;
    expectedOutputId_ = expectedOutputId;
    observedOutputId_ = 0;
    sampleRate_ = engineSampleRate;
    channels_ = 0;
    channelMask_ = 0;
    initialized_ = true;
    return true;
}

bool PcmReadbackRingV1::Begin() noexcept {
    if (!initialized_ || active_.load(std::memory_order_acquire) || sealRequested_ || sealed_ || copyAttempted_) return false;
    active_.store(true, std::memory_order_release);
    return true;
}

void PcmReadbackRingV1::InvalidateBeforeSuccessfulRegistration() noexcept {
    active_.store(false, std::memory_order_release);
    if (callbackInFlight_.test_and_set(std::memory_order_acquire)) {
        concurrentCallback_.store(true, std::memory_order_release);
        return;
    }
    formatChanged_ = true;
    sealed_ = true;
    sealRequested_ = true;
    callbackInFlight_.clear(std::memory_order_release);
}

bool PcmReadbackRingV1::ReleaseAfterEngineAndCallbackTerms() noexcept {
    active_.store(false, std::memory_order_release);
    if (callbackInFlight_.test_and_set(std::memory_order_acquire)) {
        concurrentCallback_.store(true, std::memory_order_release);
        return false;
    }
    std::free(samples_);
    samples_ = nullptr;
    initialized_ = false;
    callbackInFlight_.clear(std::memory_order_release);
    return true;
}

void PcmReadbackRingV1::SetCounterOverflow() noexcept {
    counterOverflow_ = true;
}

void PcmReadbackRingV1::Observe(const float* source, uint32_t sampleCount,
    uint32_t engineSampleRate, uint32_t channels, uint32_t channelMask,
    uint64_t callbackOutputId, bool completeBuffer) noexcept {
    if (!active_.load(std::memory_order_acquire)) return;
    if (callbackInFlight_.test_and_set(std::memory_order_acquire)) {
        concurrentCallback_.store(true, std::memory_order_release);
        return;
    }
    struct ClearFlag final {
        std::atomic_flag& flag;
        ~ClearFlag() { flag.clear(std::memory_order_release); }
    } clear{callbackInFlight_};

    if (!active_.load(std::memory_order_acquire)) return;
    if (callbacks_ == std::numeric_limits<uint64_t>::max()) SetCounterOverflow();
    else ++callbacks_;

    if (callbackOutputId == 0 || callbackOutputId == std::numeric_limits<uint64_t>::max()) {
        outputMismatch_ = true;
    } else if (!outputKnown_) {
        if (expectedOutputKnown_ && callbackOutputId != expectedOutputId_)
            outputMismatch_ = true;
        else {
            observedOutputId_ = callbackOutputId;
            outputKnown_ = true;
        }
    } else if (callbackOutputId != observedOutputId_ ||
        (expectedOutputKnown_ && callbackOutputId != expectedOutputId_)) {
        outputMismatch_ = true;
    }
    if (engineSampleRate != sampleRate_) formatChanged_ = true;
    if ((sampleCount != 0 && source == nullptr) || sampleCount > kMaxCallbackSamples ||
        channels == 0 || channels > kMaxChannels ||
        channelMask == 0 || (sampleCount % channels) != 0) {
        formatChanged_ = true;
        return;
    }
    if (channels_ == 0) { channels_ = channels; channelMask_ = channelMask; }
    else if (channels != channels_ || channelMask != channelMask_) {
        formatChanged_ = true;
        return;
    }
    if (!completeBuffer) {
        formatChanged_ = true;
        return;
    }
    if (sampleCount == 0) return;
    if (totalSamples_ > kMaxObservedSamples ||
        sampleCount > kMaxObservedSamples - totalSamples_) {
        formatChanged_ = true;
        return;
    }
    if (sampleCount > std::numeric_limits<uint64_t>::max() - totalSamples_) {
        SetCounterOverflow();
        return;
    }
    totalSamples_ += sampleCount;

    for (uint32_t index = 0; index < sampleCount; ++index) {
        const float value = source[index];
        if (!std::isfinite(value)) {
            if (nonfiniteSamples_ == std::numeric_limits<uint64_t>::max()) SetCounterOverflow();
            else ++nonfiniteSamples_;
            continue;
        }
        if (finiteSamples_ == std::numeric_limits<uint64_t>::max()) SetCounterOverflow();
        else ++finiteSamples_;
        if (value != 0.0f) {
            if (nonzeroFiniteSamples_ == std::numeric_limits<uint64_t>::max()) SetCounterOverflow();
            else ++nonzeroFiniteSamples_;
        }
        const float magnitude = std::fabs(value);
        if (magnitude > peakAbs_) peakAbs_ = magnitude;
        sumSquares_ += static_cast<double>(value) * static_cast<double>(value);

        // Preserve only a contiguous, complete-frame prefix. Never write into
        // the Wwise-owned buffer; the source pointer is read-only here.
        const uint32_t remaining = kMaxSamples - storedSamples_;
        if (remaining == 0) continue;
        samples_[storedSamples_++] = value;
        if (magnitude > storedPeakAbs_) storedPeakAbs_ = magnitude;
    }
}

PcmReadbackRingV1::Status PcmReadbackRingV1::SealAfterSuccessfulUnregister() noexcept {
    if (!initialized_) return kNotReady;
    if (sealed_) return kOk;
    if (!sealRequested_) {
        active_.store(false, std::memory_order_release);
        sealRequested_ = true;
    }
    if (callbackInFlight_.test_and_set(std::memory_order_acquire)) return kBusy;
    callbackInFlight_.clear(std::memory_order_release);
    sealed_ = true;
    return kOk;
}

bool PcmReadbackRingV1::IsWaveformValid() const noexcept {
    return initialized_ && sealed_ && outputKnown_ && !outputMismatch_ && !concurrentCallback_.load(std::memory_order_acquire) &&
        !formatChanged_ && !counterOverflow_ && nonfiniteSamples_ == 0 &&
        totalSamples_ > 0 && storedSamples_ > 0 && channels_ > 0 && channelMask_ != 0 &&
        (storedSamples_ % channels_) == 0;
}

PcmReadbackRingV1::Status PcmReadbackRingV1::ReadMetadata(uint32_t* words,
    uint32_t capacityWords) const noexcept {
    if (!sealed_ || !initialized_) return kNotReady;
    if (words == nullptr || capacityWords != kMetadataWords) return kCapacityMismatch;
    std::memset(words, 0, kMetadataWords * sizeof(uint32_t));
    uint32_t flags = outputKnown_ ? kFlagOutputKnown : 0;
    if (sampleRate_ != 0 && channels_ != 0) flags |= kFlagFormatKnown;
    if (channelMask_ != 0) flags |= kFlagChannelMaskKnown;
    if (storedSamples_ < totalSamples_) flags |= kFlagTruncated;
    if (IsWaveformValid()) flags |= kFlagWaveformValid;
    if (outputMismatch_) flags |= kFlagOutputMismatch;
    if (concurrentCallback_.load(std::memory_order_acquire)) flags |= kFlagConcurrentCallback;
    if (formatChanged_) flags |= kFlagFormatChanged;
    if (counterOverflow_) flags |= kFlagCounterOverflow;

    words[0] = kSchema;
    words[1] = flags;
    words[2] = static_cast<uint32_t>(generation_ & 0xffffffffu);
    words[3] = static_cast<uint32_t>(generation_ >> 32);
    words[4] = static_cast<uint32_t>(observedOutputId_ & 0xffffffffu);
    words[5] = static_cast<uint32_t>(observedOutputId_ >> 32);
    words[6] = sampleRate_;
    words[7] = channels_;
    words[8] = channelMask_;
    words[9] = kFloat32Format;
    words[10] = static_cast<uint32_t>(totalSamples_ & 0xffffffffu);
    words[11] = static_cast<uint32_t>(totalSamples_ >> 32);
    words[12] = storedSamples_;
    words[13] = static_cast<uint32_t>(finiteSamples_ & 0xffffffffu);
    words[14] = static_cast<uint32_t>(finiteSamples_ >> 32);
    words[15] = static_cast<uint32_t>(nonzeroFiniteSamples_ & 0xffffffffu);
    words[16] = static_cast<uint32_t>(nonzeroFiniteSamples_ >> 32);
    words[17] = static_cast<uint32_t>(nonfiniteSamples_ & 0xffffffffu);
    words[18] = static_cast<uint32_t>(nonfiniteSamples_ >> 32);
    words[19] = static_cast<uint32_t>(callbacks_ & 0xffffffffu);
    words[20] = static_cast<uint32_t>(callbacks_ >> 32);
    std::memcpy(&words[21], &peakAbs_, sizeof(float));
    const float rms = finiteSamples_ == 0 ? 0.0f :
        static_cast<float>(std::sqrt(sumSquares_ / static_cast<double>(finiteSamples_)));
    std::memcpy(&words[22], &rms, sizeof(float));
    std::memcpy(&words[23], &storedPeakAbs_, sizeof(float));
    // Prefix RMS is reconstructed by the host from the exact retained samples.
    return kOk;
}

PcmReadbackRingV1::Status PcmReadbackRingV1::CopySamples(uint64_t expectedGeneration,
    uint64_t expectedOutputId, float* destination, uint32_t capacitySamples,
    uint32_t* copiedSamples) noexcept {
    if (copiedSamples != nullptr) *copiedSamples = 0;
    if (!sealed_ || !initialized_) return kNotReady;
    if (copyAttempted_) return kAlreadyCopied;
    copyAttempted_ = true;
    if (expectedGeneration != generation_) return kWrongGeneration;
    if (expectedOutputId != observedOutputId_) return kWrongOutput;
    if (!IsWaveformValid()) return kInvalidWaveform;
    if (destination == nullptr || copiedSamples == nullptr || capacitySamples != storedSamples_)
        return kCapacityMismatch;
    std::memcpy(destination, samples_, static_cast<size_t>(storedSamples_) * sizeof(float));
    *copiedSamples = storedSamples_;
    return kOk;
}

} // namespace ror2lab_audio_diag
