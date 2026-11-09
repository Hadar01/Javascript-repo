// What does the kernel's UDP path cost?
//
// A 64-byte packet ping-pongs between two pinned threads through UDP sockets
// on 127.0.0.1. The round trip is timed with the TSC on one core, and each
// direction goes through the kernel's network stack:
//   busy-poll: non-blocking recv in a spin loop (what MoldReceiver does)
//   blocking:  the thread sleeps in poll() until a packet arrives, so every
//              packet also pays for the kernel waking the thread up
// Compare with the SPSC ring's round trip (bench/spsc_bench.cpp), which never
// enters the kernel. The gap is why trading firms use kernel-bypass
// networking (Solarflare/OpenOnload, ef_vi, DPDK, AF_XDP): the NIC delivers
// packets straight into the application's memory.

#include <benchmark/benchmark.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <thread>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/net/udp_socket.hpp"

namespace {

using hft::net::Endpoint;
using hft::net::UdpSocket;

constexpr int kMainCpu = 2;
constexpr int kEchoCpu = 3;

sockaddr_in loopback(std::uint16_t port) {
  Endpoint ep{.ip = "127.0.0.1", .port = port};
  return ep.to_sockaddr();
}

template <bool kBlocking>
void BM_UdpRoundTrip(benchmark::State& state) {
  static const hft::TscClock tsc = hft::TscClock::calibrate(50);
  UdpSocket a = UdpSocket::open_receiver(Endpoint::parse("127.0.0.1:0"), 1 << 20);
  UdpSocket b = UdpSocket::open_receiver(Endpoint::parse("127.0.0.1:0"), 1 << 20);
  const sockaddr_in to_a = loopback(a.local_port());
  const sockaddr_in to_b = loopback(b.local_port());

  std::atomic<bool> stop{false};
  std::thread echo([&] {
    hft::pin_current_thread(kEchoCpu);
    std::array<std::byte, 256> buf{};
    while (!stop.load(std::memory_order_relaxed)) {
      const std::ptrdiff_t n = kBlocking ? b.recv_blocking(buf) : b.try_recv(buf);
      if (n > 0) {
        (void)b.send_to(std::span<const std::byte>(buf.data(), static_cast<std::size_t>(n)), to_a);
      } else if (!kBlocking) {
        hft::cpu_relax();
      }
    }
  });
  hft::pin_current_thread(kMainCpu);

  const std::array<std::byte, 64> payload{};
  std::array<std::byte, 256> buf{};
  std::vector<std::uint64_t> rtt(static_cast<std::size_t>(state.max_iterations));
  std::size_t n = 0;
  for (auto _ : state) {
    const std::uint64_t t0 = hft::rdtsc();
    (void)a.send_to(payload, to_b);
    if constexpr (kBlocking) {
      (void)a.recv_blocking(buf);
    } else {
      while (a.try_recv(buf) <= 0) hft::cpu_relax();
    }
    rtt[n++] = hft::rdtsc() - t0;
  }
  stop.store(true, std::memory_order_relaxed);
  (void)a.send_to(payload, to_b);  // wake the echo thread if it is asleep in poll()
  echo.join();

  std::sort(rtt.begin(), rtt.begin() + static_cast<std::ptrdiff_t>(n));
  auto pct = [&](double p) {
    return tsc.to_ns(rtt[std::min(n - 1, static_cast<std::size_t>(p * static_cast<double>(n)))]);
  };
  state.counters["rtt_p50_us"] = pct(0.50) / 1000;
  state.counters["rtt_p99_us"] = pct(0.99) / 1000;
}

BENCHMARK(BM_UdpRoundTrip<false>)->Name("BM_UdpRoundTrip/busy_poll")->Iterations(100'000)->Repetitions(3)->ReportAggregatesOnly(true);
BENCHMARK(BM_UdpRoundTrip<true>)->Name("BM_UdpRoundTrip/blocking")->Iterations(100'000)->Repetitions(3)->ReportAggregatesOnly(true);

}  // namespace
