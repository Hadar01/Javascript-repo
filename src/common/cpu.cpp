#include "hft/common/cpu.hpp"

#include <pthread.h>
#include <sched.h>

#include <chrono>
#include <thread>

namespace hft {

bool pin_current_thread(int cpu) noexcept {
  if (cpu < 0) return true;
  if (cpu >= CPU_SETSIZE) return false;
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(static_cast<std::size_t>(cpu), &set);
  return pthread_setaffinity_np(pthread_self(), sizeof set, &set) == 0;
}

TscClock TscClock::calibrate(int milliseconds) {
  using clock = std::chrono::steady_clock;
  const auto t0 = clock::now();
  const std::uint64_t c0 = rdtsc();
  std::this_thread::sleep_for(std::chrono::milliseconds(milliseconds));
  const std::uint64_t c1 = rdtsc();
  const auto t1 = clock::now();
  const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count();
  const double ticks = static_cast<double>(c1 - c0);
  return TscClock(ticks > 0 ? ticks / ns : 1.0);
}

}  // namespace hft
