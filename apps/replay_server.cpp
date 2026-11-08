// replay_server: send an ITCH file over UDP the way an exchange does.
//
//   replay_server FILE --group IP:PORT [--group-b IP:PORT] [--speed X]
//                 [--max-payload N] [--drop-a P] [--drop-b P] [--cpu N]
//                 [--heartbeat-ms N] [--seed N]
//
// Messages are packed into MoldUDP64 packets and sent at the moment they
// originally happened (their ITCH timestamps), scaled by --speed:
//   --speed 1    real time (a full Nasdaq day takes 16 hours)
//   --speed 100  100 times faster
//   --speed 0    no pacing: as fast as the socket accepts
// Messages due within 1 us of each other share a packet. A packet is sent
// as soon as the next message is not yet due, or when it is full, so no
// message waits for a packet to fill.
//
// --group-b sends every packet on a second line too (A/B feeds).
// --drop-a / --drop-b drop that fraction of packets on purpose on each line,
// to exercise the receiver's gap detection and A/B arbitration.

#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>

#include "hft/common/cpu.hpp"
#include "hft/common/latency_recorder.hpp"
#include "hft/common/mapped_file.hpp"
#include "hft/common/types.hpp"
#include "hft/itch/framing.hpp"
#include "hft/itch/messages.hpp"
#include "hft/itch/wire.hpp"
#include "hft/net/moldudp64.hpp"
#include "hft/net/udp_socket.hpp"

namespace {

using hft::net::Endpoint;

struct Options {
  std::string file;
  std::optional<Endpoint> line_a;
  std::optional<Endpoint> line_b;
  double speed = 1.0;
  std::size_t max_payload = 1372;  // this container's MTU is 1400; 1472 for MTU 1500
  double drop[2] = {0.0, 0.0};
  int cpu = 1;
  int heartbeat_ms = 1000;
  std::uint64_t seed = 7;
};

template <typename T>
bool parse_number(std::string_view s, T& out) {
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

int usage() {
  std::fprintf(stderr,
               "usage: replay_server FILE --group IP:PORT [--group-b IP:PORT] [--speed X] [--max-payload N]\n"
               "                     [--drop-a P] [--drop-b P] [--cpu N] [--heartbeat-ms N] [--seed N]\n");
  return 2;
}

// SplitMix64, for repeatable simulated loss.
struct Rng {
  std::uint64_t state;
  double uniform() noexcept {
    std::uint64_t z = (state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    z ^= z >> 31;
    return static_cast<double>(z >> 11) * 0x1.0p-53;  // 53 random bits -> [0, 1)
  }
};

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  Options opt;
  opt.file = argv[1];
  try {
    for (int i = 2; i < argc; ++i) {
      const std::string_view flag = argv[i];
      if (i + 1 >= argc) return usage();
      const std::string_view v = argv[++i];
      bool ok = true;
      if (flag == "--group") opt.line_a = Endpoint::parse(v);
      else if (flag == "--group-b") opt.line_b = Endpoint::parse(v);
      else if (flag == "--speed") ok = parse_number(v, opt.speed) && opt.speed >= 0;
      else if (flag == "--max-payload") ok = parse_number(v, opt.max_payload) && opt.max_payload > 64;
      else if (flag == "--drop-a") ok = parse_number(v, opt.drop[0]);
      else if (flag == "--drop-b") ok = parse_number(v, opt.drop[1]);
      else if (flag == "--cpu") ok = parse_number(v, opt.cpu);
      else if (flag == "--heartbeat-ms") ok = parse_number(v, opt.heartbeat_ms);
      else if (flag == "--seed") ok = parse_number(v, opt.seed);
      else ok = false;
      if (!ok) return usage();
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "replay_server: %s\n", e.what());
    return usage();
  }
  if (!opt.line_a) return usage();

  try {
    const hft::MappedFile file(opt.file);
    const auto tsc = hft::TscClock::calibrate();
    hft::pin_current_thread(opt.cpu);
    hft::net::UdpSocket sock = hft::net::UdpSocket::open_sender();
    const sockaddr_in dest[2] = {opt.line_a->to_sockaddr(), opt.line_b ? opt.line_b->to_sockaddr() : sockaddr_in{}};
    const int lines = opt.line_b ? 2 : 1;

    hft::net::Session session;
    std::memcpy(session.data(), "HFTLOB0001", session.size());
    hft::net::PacketBuilder builder(session, opt.max_payload);
    Rng rng{opt.seed};

    std::uint64_t packets = 0, messages = 0, bytes = 0, heartbeats = 0, send_failures = 0;
    std::uint64_t dropped[2] = {0, 0};
    hft::LatencyRecorder lateness(std::size_t{4} << 20);

    std::uint64_t last_send_tsc = hft::rdtsc();
    auto send_packet = [&](std::span<const std::byte> packet) {
      for (int l = 0; l < lines; ++l) {
        if (opt.drop[l] > 0 && rng.uniform() < opt.drop[l]) {
          ++dropped[l];  // simulated loss on this line
          continue;
        }
        if (!sock.send_to(packet, dest[l])) ++send_failures;
      }
      last_send_tsc = hft::rdtsc();
    };

    const double ticks_per_ns = tsc.ticks_per_ns();
    const auto heartbeat_ticks = static_cast<std::uint64_t>(opt.heartbeat_ms * 1e6 * ticks_per_ns);
    const auto coalesce_ticks = static_cast<std::uint64_t>(1000 * ticks_per_ns);  // 1 us
    bool have_first = false;
    hft::Timestamp first_ts = 0, last_ts = 0;
    std::uint64_t start_tsc = 0;
    std::uint64_t packet_due = 0;  // due time of the first message in the current packet

    auto flush = [&] {
      if (builder.empty()) return;
      ++packets;
      messages += builder.count();
      if (opt.speed > 0) {
        const std::uint64_t now = hft::rdtsc();
        lateness.record(now > packet_due ? now - packet_due : 0);
      }
      const auto packet = builder.finish();
      bytes += packet.size();
      send_packet(packet);
    };

    // Wait until `due`, sending heartbeats if the wait is long. Long waits
    // sleep first: spinning through a 30-second quiet spell would only burn
    // a core.
    auto wait_until = [&](std::uint64_t due) {
      while (true) {
        const std::uint64_t now = hft::rdtsc();
        if (now >= due) return;
        if (now - last_send_tsc >= heartbeat_ticks) {
          ++heartbeats;
          send_packet(builder.control(hft::net::kMoldHeartbeat));
        }
        const double remaining_ns = static_cast<double>(due - now) / ticks_per_ns;
        if (remaining_ns > 2e6) {
          std::this_thread::sleep_for(std::chrono::nanoseconds(static_cast<std::int64_t>(remaining_ns - 1e6)));
        } else {
          hft::cpu_relax();
        }
      }
    };

    std::printf("replaying %s to %s:%u%s at speed %g\n", opt.file.c_str(), opt.line_a->ip.c_str(), opt.line_a->port,
                opt.line_b ? " and line B" : "", opt.speed);
    const auto wall0 = std::chrono::steady_clock::now();

    hft::itch::for_each_framed(file.bytes(), [&](std::span<const std::byte> msg) {
      // Every ITCH message has a 48-bit timestamp at offset 5.
      if (msg.size() >= hft::itch::kHeaderSize) last_ts = hft::itch::load_be48(msg.data() + 5);
      if (!have_first) {
        have_first = true;
        first_ts = last_ts;
        start_tsc = hft::rdtsc();
      }
      std::uint64_t due = 0;
      if (opt.speed > 0) {
        // Guard the subtraction: unsigned, so an out-of-order timestamp would
        // wrap to a huge number and the server would wait for centuries.
        const hft::Timestamp since_first = last_ts > first_ts ? last_ts - first_ts : 0;
        const double offset_ns = static_cast<double>(since_first) / opt.speed;
        due = start_tsc + static_cast<std::uint64_t>(offset_ns * ticks_per_ns);
        // Not due yet (beyond the coalescing window): send what we have now,
        // so it isn't held back waiting for this message.
        if (due > hft::rdtsc() + coalesce_ticks) {
          flush();
          wait_until(due);
        }
      }
      if (!builder.fits(msg.size())) flush();
      if (builder.empty()) packet_due = due;
      builder.add(msg);
    });
    flush();

    // End of session, sent a few times: a single lost copy would leave
    // receivers waiting for their idle timeout.
    for (int i = 0; i < 3; ++i) {
      send_packet(builder.control(hft::net::kMoldEndOfSession));
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - wall0).count();
    std::printf("sent            %llu messages in %llu packets (%.1f msgs/packet, %.1f MB) in %.3f s\n",
                static_cast<unsigned long long>(messages), static_cast<unsigned long long>(packets),
                packets ? static_cast<double>(messages) / static_cast<double>(packets) : 0.0,
                static_cast<double>(bytes) / 1e6, secs);
    std::printf("rate            %.2f M msgs/s, %.0f k packets/s per line\n",
                static_cast<double>(messages) / secs / 1e6, static_cast<double>(packets) / secs / 1e3);
    std::printf("heartbeats      %llu   send failures %llu\n", static_cast<unsigned long long>(heartbeats),
                static_cast<unsigned long long>(send_failures));
    std::printf("simulated loss  line A %llu packets%s\n", static_cast<unsigned long long>(dropped[0]),
                lines == 2 ? (", line B " + std::to_string(dropped[1]) + " packets").c_str() : "");
    if (opt.speed > 0) {
      const auto s = lateness.summarize(tsc);
      std::printf("pacing          packet sent later than due: p50 %.0f ns  p99 %.0f ns  max %.0f ns\n", s.p50_ns,
                  s.p99_ns, s.max_ns);
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "replay_server: %s\n", e.what());
    return 1;
  }
  return 0;
}
