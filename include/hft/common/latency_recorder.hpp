#pragma once

// LatencyRecorder: collect raw latency samples on the hot path, compute
// percentiles afterwards.
//
// The sample buffer is allocated AND written once in the constructor.
// reserve() alone isn't enough: it allocates address space, but the kernel
// maps each 4 KB page only on its first write, so recording would take a
// page fault every 512 samples, stalling the thread for microseconds each
// time. That showed up as the p99 of the ring hop (measured; see
// LEARNING.md, stage 2). When the buffer is full, further samples are
// counted, not stored.
//
// Storing every sample and sorting at the end gives exact percentiles. A
// histogram (fixed buckets) would use less memory and could report while
// running, at the cost of bucket-width precision. Stage 5 may switch.
//
// Why percentiles: latency distributions have long tails (a cache miss, an
// interrupt, a page fault). The mean hides them, and in trading the slow
// cases are the ones that lose money. Report the median AND the tail.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

#include "hft/common/cpu.hpp"

namespace hft {

class LatencyRecorder {
 public:
  // Value-initialising writes zeros to every element, which faults in every page now.
  explicit LatencyRecorder(std::size_t capacity) : samples_(capacity) {}

  void record(std::uint64_t ticks) noexcept {
    if (count_ < samples_.size()) {
      samples_[count_++] = ticks;
    } else {
      ++overflow_;
    }
  }

  struct Summary {
    std::size_t count = 0;
    double p50_ns = 0, p90_ns = 0, p99_ns = 0, p999_ns = 0, max_ns = 0;
  };

  // Sorts a copy, so it allocates: call it after the measured run.
  [[nodiscard]] Summary summarize(const TscClock& clock) const {
    Summary s;
    s.count = count_;
    if (count_ == 0) return s;
    std::vector<std::uint64_t> sorted(samples_.begin(), samples_.begin() + static_cast<std::ptrdiff_t>(count_));
    std::sort(sorted.begin(), sorted.end());
    // Nearest-rank percentile: the smallest sample with at least p of the
    // samples at or below it.
    auto at = [&](double p) {
      const auto rank = static_cast<std::size_t>(std::ceil(p * static_cast<double>(sorted.size())));
      return clock.to_ns(sorted[std::max<std::size_t>(rank, 1) - 1]);
    };
    s.p50_ns = at(0.50);
    s.p90_ns = at(0.90);
    s.p99_ns = at(0.99);
    s.p999_ns = at(0.999);
    s.max_ns = clock.to_ns(sorted.back());
    return s;
  }

  [[nodiscard]] std::size_t size() const noexcept { return count_; }
  [[nodiscard]] std::uint64_t overflow() const noexcept { return overflow_; }

 private:
  std::vector<std::uint64_t> samples_;
  std::size_t count_ = 0;
  std::uint64_t overflow_ = 0;
};

}  // namespace hft
