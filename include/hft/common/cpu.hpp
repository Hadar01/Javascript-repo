#pragma once

// Small CPU-level utilities for the threaded parts of the pipeline:
// spinning politely, pinning a thread to a core, and cheap timestamps.

#include <cstddef>
#include <cstdint>

#if defined(__x86_64__)
#include <x86intrin.h>
#endif

namespace hft {

// Two objects closer than this can share a cache line (or a pair of lines),
// so writes to one slow down the other core using the other. That is "false
// sharing". Intel CPUs prefetch cache lines in adjacent pairs, so two
// different 64-byte lines can still interfere; 128 avoids both cases.
// std::hardware_destructive_interference_size exists, but GCC warns that its
// value may change with compiler flags, which would silently change the
// layout of our types.
inline constexpr std::size_t kNoFalseSharing = 128;

// Gives a value a cache-line block of its own, so writes to the neighbours
// it would otherwise have can't slow down the core that reads it.
template <typename T>
struct alignas(kNoFalseSharing) CachePadded {
  T value{};
};

// Body of a busy-wait loop. On x86, PAUSE tells the CPU this is a spin loop:
// it uses less power, lets a hyperthread sibling run, and avoids a pipeline
// flush when the loop finally exits. Note: on recent Intel server CPUs one
// PAUSE takes ~140 cycles, which adds directly to wake-up latency.
inline void cpu_relax() noexcept {
#if defined(__x86_64__)
  _mm_pause();
#elif defined(__aarch64__)
  asm volatile("yield" ::: "memory");
#endif
}

// Pin the calling thread to one CPU, so the scheduler never moves it (a move
// costs a cold cache and microseconds of latency). Returns false if the CPU
// doesn't exist or isn't allowed for this process. cpu < 0 does nothing.
bool pin_current_thread(int cpu) noexcept;

// Read the CPU's time-stamp counter: ~15 ns here, against ~27 ns for
// std::chrono::steady_clock. The counter runs at a fixed rate on CPUs with
// constant_tsc/nonstop_tsc, and is synchronised across cores, so a value
// taken on one core can be compared with a value taken on another.
inline std::uint64_t rdtsc() noexcept {
#if defined(__x86_64__)
  return __rdtsc();
#else
  return 0;  // not supported: latency numbers will read as zero
#endif
}

// Converts TSC ticks to nanoseconds. calibrate() counts ticks against
// steady_clock for a short while at startup, never on the hot path.
class TscClock {
 public:
  static TscClock calibrate(int milliseconds = 100);
  [[nodiscard]] double ticks_per_ns() const noexcept { return ticks_per_ns_; }
  [[nodiscard]] double to_ns(std::uint64_t ticks) const noexcept {
    return static_cast<double>(ticks) / ticks_per_ns_;
  }

 private:
  explicit TscClock(double ticks_per_ns) : ticks_per_ns_(ticks_per_ns) {}
  double ticks_per_ns_;
};

}  // namespace hft
