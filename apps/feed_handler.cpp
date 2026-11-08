// feed_handler: receive a MoldUDP64/ITCH feed from the network and run the
// two-thread pipeline on it.
//
//   feed_handler --group IP:PORT [--group-b IP:PORT] --symbols SYM[,SYM...]
//                [--net-cpu N] [--strategy-cpu N] [--rcvbuf BYTES] [--wait]
//                [--max-orders N] [--idle-timeout-ms N]
//
// Network thread (--net-cpu): recv -> MoldUDP64 -> sequence check / A-B
//   arbitration -> ITCH parse -> book -> snapshot -> ring.
// Strategy thread (--strategy-cpu): pops snapshots and measures the ring hop.
//
// Start this first, then replay_server: UDP has no backlog, so anything sent
// before the receiver joins the group is simply gone.

#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/common/latency_recorder.hpp"
#include "hft/feed/feed_handler.hpp"
#include "hft/feed/measuring_consumer.hpp"
#include "hft/feed/pipeline.hpp"
#include "hft/net/mold_receiver.hpp"
#include "hft/net/udp_socket.hpp"

namespace {

using hft::feed::BookUpdate;
using hft::net::Endpoint;

template <typename T>
bool parse_number(std::string_view s, T& out) {
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

int usage() {
  std::fprintf(stderr,
               "usage: feed_handler --group IP:PORT [--group-b IP:PORT] --symbols SYM[,SYM...] [--net-cpu N]\n"
               "                    [--strategy-cpu N] [--rcvbuf BYTES] [--wait] [--max-orders N]\n"
               "                    [--idle-timeout-ms N] [--window-us N] [--late-join]\n");
  return 2;
}

std::string top_of_book(const BookUpdate& u) {
  char buf[96];
  if (u.bid_depth == 0 || u.ask_depth == 0) return "(one side empty)";
  std::snprintf(buf, sizeof buf, "%u x %u.%04u  /  %u.%04u x %u", u.bids[0].qty, u.bids[0].price / 10'000,
                u.bids[0].price % 10'000, u.asks[0].price / 10'000, u.asks[0].price % 10'000, u.asks[0].qty);
  return buf;
}

unsigned long long ull(std::uint64_t v) { return static_cast<unsigned long long>(v); }

}  // namespace

int main(int argc, char** argv) {
  std::optional<Endpoint> line_a, line_b;
  std::vector<std::string> symbols;
  int rcvbuf = 4 << 20;
  hft::net::ReceiverConfig rcfg;
  hft::feed::FeedHandlerConfig cfg{.book = {.max_orders = std::size_t{4} << 20, .levels_per_side = 64},
                                   .on_full = hft::feed::OnFull::Drop};
  hft::feed::PipelineConfig pcfg{.feed_cpu = 2, .strategy_cpu = 3};

  try {
    for (int i = 1; i < argc; ++i) {
      const std::string_view flag = argv[i];
      if (flag == "--wait") {
        cfg.on_full = hft::feed::OnFull::Wait;
        continue;
      }
      if (flag == "--late-join") {
        // Joining a session already in progress: don't count everything
        // before the first packet as lost.
        rcfg.first_seq = 0;
        continue;
      }
      if (i + 1 >= argc) return usage();
      const std::string_view v = argv[++i];
      bool ok = true;
      if (flag == "--group") line_a = Endpoint::parse(v);
      else if (flag == "--group-b") line_b = Endpoint::parse(v);
      else if (flag == "--net-cpu") ok = parse_number(v, pcfg.feed_cpu);
      else if (flag == "--strategy-cpu") ok = parse_number(v, pcfg.strategy_cpu);
      else if (flag == "--rcvbuf") ok = parse_number(v, rcvbuf);
      else if (flag == "--max-orders") ok = parse_number(v, cfg.book.max_orders);
      else if (flag == "--idle-timeout-ms") ok = parse_number(v, rcfg.idle_timeout_ms);
      else if (flag == "--window-us") ok = parse_number(v, rcfg.arbitration_window_us);
      else if (flag == "--symbols") {
        std::size_t start = 0;
        while (start <= v.size()) {
          const std::size_t comma = v.find(',', start);
          const auto end = comma == std::string_view::npos ? v.size() : comma;
          if (end > start) symbols.emplace_back(v.substr(start, end - start));
          start = end + 1;
        }
      } else {
        ok = false;
      }
      if (!ok) return usage();
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "feed_handler: %s\n", e.what());
    return usage();
  }
  if (!line_a || symbols.empty()) return usage();

  try {
    const auto tsc = hft::TscClock::calibrate();
    hft::net::UdpSocket sock_a = hft::net::UdpSocket::open_receiver(*line_a, rcvbuf);
    std::optional<hft::net::UdpSocket> sock_b;
    if (line_b) sock_b = hft::net::UdpSocket::open_receiver(*line_b, rcvbuf);
    std::vector<hft::net::UdpSocket*> lines{&sock_a};
    if (sock_b) lines.push_back(&*sock_b);

    auto ring = std::make_unique<hft::feed::UpdateRing>();
    auto handler = std::make_unique<hft::feed::FeedHandler>(cfg, *ring);
    for (const auto& s : symbols) handler->subscribe_ticker(s);
    hft::LatencyRecorder latency(std::size_t{8} << 20);
    hft::feed::MeasuringConsumer strategy{.latency = latency, .latest = {}};
    strategy.latest.reserve(symbols.size());
    auto receiver = std::make_unique<hft::net::MoldReceiver>(rcfg);

    std::printf("listening on %s:%u%s (receive buffer granted: %d bytes)\n", line_a->ip.c_str(), line_a->port,
                line_b ? (" and " + line_b->ip + ":" + std::to_string(line_b->port)).c_str() : "", sock_a.rcvbuf());
    std::fflush(stdout);

    const auto udp0 = hft::net::read_udp_counters();
    const auto t0 = std::chrono::steady_clock::now();
    const auto run = hft::feed::run_with_strategy(
        [&] { return receiver->run(std::span<hft::net::UdpSocket* const>(lines), *handler); }, *ring, strategy, pcfg);
    const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    const auto udp1 = hft::net::read_udp_counters();

    const auto& r = run.feed;
    const auto& seq = r.sequence;
    const auto& pub = handler->stats();
    const auto& book = handler->book().stats();
    const auto lat = latency.summarize(tsc);
    std::printf("threads         network on cpu %d (%s), strategy on cpu %d (%s)\n", pcfg.feed_cpu,
                run.feed_pinned ? "pinned" : "NOT pinned", pcfg.strategy_cpu,
                run.strategy_pinned ? "pinned" : "NOT pinned");
    std::printf("stopped by      %s after %.3f s\n",
                r.end_of_session ? "end of session" : (r.idle_timeout ? "idle timeout" : "stop request"), secs);
    std::printf("packets         line A %llu%s   heartbeats %llu   malformed %llu\n", ull(r.packets[0]),
                line_b ? ("   line B " + std::to_string(r.packets[1])).c_str() : "", ull(r.heartbeats),
                ull(r.malformed_packets));
    std::printf("sequence        duplicates %llu   overlaps %llu   gaps %llu (%llu messages lost)\n",
                ull(seq.duplicate_packets), ull(seq.overlap_packets), ull(seq.gap_events), ull(seq.gap_messages));
    if (line_b) {
      std::printf("arbitration     waited for the other line %llu times, gave up %llu times\n",
                  ull(r.arbitration_waits), ull(r.arbitration_timeouts));
    }
    std::printf("kernel          UDP receive-buffer overflows during the run: %llu\n",
                ull(udp1.rcvbuf_errors - udp0.rcvbuf_errors));
    std::printf("itch            %llu messages   skipped types %llu   malformed %llu\n", ull(r.itch.messages),
                ull(r.itch.unknown_type), ull(r.itch.malformed));
    std::printf("book anomalies  unknown order %llu   duplicate %llu   overfill %llu  (non-zero after lost messages)\n",
                ull(book.unknown_order), ull(book.duplicate_order), ull(book.overfill));
    std::printf("updates         published %llu   unchanged %llu   dropped %llu\n", ull(pub.published),
                ull(pub.unchanged), ull(pub.dropped));
    std::printf("strategy        received %llu   sequence gaps %llu   clock skew %llu\n", ull(strategy.received),
                ull(strategy.gaps), ull(strategy.clock_skew));
    std::printf("ring hop (ns)   p50 %.0f  p90 %.0f  p99 %.0f  p99.9 %.0f  max %.0f  (%zu samples)\n", lat.p50_ns,
                lat.p90_ns, lat.p99_ns, lat.p999_ns, lat.max_ns, lat.count);
    for (const auto& s : symbols) {
      const auto loc = handler->book().find_locate(s);
      if (!loc) {
        std::printf("%-8s not in the stock directory\n", s.c_str());
        continue;
      }
      const BookUpdate truth = handler->snapshot(*loc);
      const BookUpdate* seen = strategy.find(*loc);
      std::printf("%-8s book %s   strategy's view %s\n", s.c_str(), top_of_book(truth).c_str(),
                  seen != nullptr && hft::feed::same_levels(*seen, truth) ? "matches" : "differs");
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "feed_handler: %s\n", e.what());
    return 1;
  }
  return 0;
}
