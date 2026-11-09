// What does it cost to read the clock?
//
// Every latency number in this project comes from reading a clock twice and
// subtracting. If one read costs 20 ns, a stage that takes 50 ns can't be
// measured to better than that. So we measure the ruler before we measure
// anything with it.

#include <benchmark/benchmark.h>

#include <chrono>
#include <cstdint>

#if defined(__x86_64__)
#include <x86intrin.h>
#endif

namespace {

// std::chrono::steady_clock calls clock_gettime(CLOCK_MONOTONIC). On Linux
// that runs in user space via the vDSO (no system call), as long as the kernel
// clock source is "tsc".
void BM_SteadyClockNow(benchmark::State& state) {
  for (auto _ : state) {
    auto t = std::chrono::steady_clock::now();
    benchmark::DoNotOptimize(t);
  }
}
BENCHMARK(BM_SteadyClockNow);

#if defined(__x86_64__)
// RDTSC reads the CPU's time-stamp counter directly: one instruction, no
// kernel. It returns ticks, not nanoseconds, so you need a calibrated
// ticks-per-ns factor to convert. The CPU may also execute it out of order,
// before or after the code you meant to time.
void BM_Rdtsc(benchmark::State& state) {
  for (auto _ : state) {
    std::uint64_t t = __rdtsc();
    benchmark::DoNotOptimize(t);
  }
}
BENCHMARK(BM_Rdtsc);

// RDTSCP waits until all earlier instructions have executed before it reads
// the counter, so the code you're timing can't slip past it. That costs a
// little more per read.
void BM_Rdtscp(benchmark::State& state) {
  unsigned int cpu_id = 0;  // RDTSCP also returns which core it ran on
  for (auto _ : state) {
    std::uint64_t t = __rdtscp(&cpu_id);
    benchmark::DoNotOptimize(t);
  }
  benchmark::DoNotOptimize(cpu_id);
}
BENCHMARK(BM_Rdtscp);
#endif

}  // namespace
