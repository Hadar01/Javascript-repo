// SPSC ring benchmarks: throughput and round-trip latency between two
// pinned cores, for the real ring and for variants that each change ONE
// thing, so each difference measures one design decision:
//
//   SpscRing           the real one: padded, cached indices
//   Control            Variant with the same settings as SpscRing. It should
//                      score the same; the gap between the two is the noise
//                      of the measurement itself
//   Unpadded           producer and consumer fields on the same cache line
//   NoCache            reads the other side's index on every operation
//   Locked             a std::mutex around a plain ring
//
// Results on the cloud VM vary ~15% run to run; each benchmark repeats 3
// times and reports the median.
//
// Threads: producer on kProducerCpu, consumer on kConsumerCpu. On this
// machine they are separate physical cores, so every handoff crosses cores.

#include <benchmark/benchmark.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/concurrency/spsc_ring.hpp"

namespace {

constexpr int kProducerCpu = 2;
constexpr int kConsumerCpu = 3;
constexpr std::size_t kCap = 1024;

// The same algorithm as SpscRing, with the two design decisions as switches.
template <typename T, std::size_t N, bool kPadded, bool kCacheIndex>
class Variant {
  static constexpr std::size_t kAlign = kPadded ? hft::kNoFalseSharing : alignof(std::atomic<std::uint64_t>);
  struct alignas(kAlign) Side {
    std::atomic<std::uint64_t> index{0};
    std::uint64_t cache = 0;
  };

 public:
  bool try_push(const T& v) noexcept {
    const std::uint64_t w = prod_.index.load(std::memory_order_relaxed);
    if constexpr (kCacheIndex) {
      if (w - prod_.cache == N) {
        prod_.cache = cons_.index.load(std::memory_order_acquire);
        if (w - prod_.cache == N) return false;
      }
    } else {
      if (w - cons_.index.load(std::memory_order_acquire) == N) return false;
    }
    slots_[w & (N - 1)] = v;
    prod_.index.store(w + 1, std::memory_order_release);
    return true;
  }
  bool try_pop(T& out) noexcept {
    const std::uint64_t r = cons_.index.load(std::memory_order_relaxed);
    if constexpr (kCacheIndex) {
      if (r == cons_.cache) {
        cons_.cache = prod_.index.load(std::memory_order_acquire);
        if (r == cons_.cache) return false;
      }
    } else {
      if (r == prod_.index.load(std::memory_order_acquire)) return false;
    }
    out = slots_[r & (N - 1)];
    cons_.index.store(r + 1, std::memory_order_release);
    return true;
  }

 private:
  Side prod_;
  Side cons_;
  alignas(kAlign) std::array<T, N> slots_{};
};

template <typename T, std::size_t N>
class MutexRing {
 public:
  bool try_push(const T& v) {
    std::lock_guard lock(m_);
    if (w_ - r_ == N) return false;
    slots_[w_++ & (N - 1)] = v;
    return true;
  }
  bool try_pop(T& out) {
    std::lock_guard lock(m_);
    if (w_ == r_) return false;
    out = slots_[r_++ & (N - 1)];
    return true;
  }

 private:
  std::mutex m_;
  std::uint64_t w_ = 0;
  std::uint64_t r_ = 0;
  std::array<T, N> slots_{};
};

using Real = hft::SpscRing<std::uint64_t, kCap>;
using Unpadded = Variant<std::uint64_t, kCap, false, true>;
using NoCache = Variant<std::uint64_t, kCap, true, false>;
using Locked = MutexRing<std::uint64_t, kCap>;
using Control = Variant<std::uint64_t, kCap, true, true>;

// Throughput: stream kItems integers from one core to the other. Thread
// start-up is excluded: both threads wait on `go` first. The time is the
// producer's start to the consumer's last item (UseManualTime).
template <typename Ring>
void BM_Throughput(benchmark::State& state) {
  constexpr std::uint64_t kItems = std::uint64_t{1} << 22;  // 4M
  double total_ns = 0;
  for (auto _ : state) {
    auto ring = std::make_unique<Ring>();
    std::atomic<bool> go{false};
    std::uint64_t sum = 0;
    std::chrono::steady_clock::time_point end;
    std::thread consumer([&] {
      hft::pin_current_thread(kConsumerCpu);
      while (!go.load(std::memory_order_acquire)) hft::cpu_relax();
      std::uint64_t v = 0;
      for (std::uint64_t got = 0; got < kItems;) {
        if (ring->try_pop(v)) {
          sum += v;
          ++got;
        } else {
          hft::cpu_relax();
        }
      }
      end = std::chrono::steady_clock::now();
    });
    hft::pin_current_thread(kProducerCpu);
    const auto start = std::chrono::steady_clock::now();
    go.store(true, std::memory_order_release);
    for (std::uint64_t i = 0; i < kItems; ++i) {
      while (!ring->try_push(i)) hft::cpu_relax();
    }
    consumer.join();
    const double secs = std::chrono::duration<double>(end - start).count();
    state.SetIterationTime(secs);
    total_ns += secs * 1e9;
    if (sum != kItems * (kItems - 1) / 2) state.SkipWithError("items lost or duplicated");
  }
  // iterations() is signed; convert both factors to double before multiplying.
  const double items = static_cast<double>(kItems) * static_cast<double>(state.iterations());
  state.counters["ns_per_item"] = total_ns / items;
  state.counters["M_items_per_s"] = items / total_ns * 1e3;
}

// Round trip: send a number through `ping`, an echo thread sends it back
// through `pong`. Timed with the TSC on ONE core, so cross-core clock sync
// doesn't matter. One-way latency is roughly half the round trip.
template <typename Ring>
void BM_RoundTrip(benchmark::State& state) {
  static const hft::TscClock tsc = hft::TscClock::calibrate(50);
  auto ping = std::make_unique<Ring>();
  auto pong = std::make_unique<Ring>();
  std::atomic<bool> stop{false};
  std::thread echo([&] {
    hft::pin_current_thread(kConsumerCpu);
    std::uint64_t v = 0;
    while (!stop.load(std::memory_order_relaxed)) {
      if (ping->try_pop(v)) {
        while (!pong->try_push(v)) hft::cpu_relax();
      } else {
        hft::cpu_relax();
      }
    }
  });
  hft::pin_current_thread(kProducerCpu);

  std::vector<std::uint64_t> rtt(static_cast<std::size_t>(state.max_iterations));
  std::size_t n = 0;
  std::uint64_t i = 0;
  for (auto _ : state) {
    const std::uint64_t t0 = hft::rdtsc();
    while (!ping->try_push(i)) hft::cpu_relax();
    std::uint64_t v = 0;
    while (!pong->try_pop(v)) hft::cpu_relax();
    rtt[n++] = hft::rdtsc() - t0;
    ++i;
  }
  stop.store(true, std::memory_order_relaxed);
  echo.join();

  std::sort(rtt.begin(), rtt.begin() + static_cast<std::ptrdiff_t>(n));
  auto pct = [&](double p) {
    return tsc.to_ns(rtt[std::min(n - 1, static_cast<std::size_t>(p * static_cast<double>(n)))]);
  };
  state.counters["rtt_p50_ns"] = pct(0.50);
  state.counters["rtt_p99_ns"] = pct(0.99);
}

#define HFT_SPSC_BENCH(Ring)                                                                   \
  BENCHMARK(BM_Throughput<Ring>)->UseManualTime()->Unit(benchmark::kMillisecond)->Iterations(5)  \
      ->Repetitions(3)->ReportAggregatesOnly(true);                                               \
  BENCHMARK(BM_RoundTrip<Ring>)->Iterations(200'000)->Repetitions(3)->ReportAggregatesOnly(true);

HFT_SPSC_BENCH(Real)
HFT_SPSC_BENCH(Control)
HFT_SPSC_BENCH(Unpadded)
HFT_SPSC_BENCH(NoCache)
HFT_SPSC_BENCH(Locked)

}  // namespace
