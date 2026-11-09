// pipeline: replay an ITCH file through the two-thread pipeline.
//
//   pipeline FILE --symbols SYM[,SYM...] [--feed-cpu N] [--strategy-cpu N]
//                 [--wait] [--max-orders N]
//
// Feed thread: parse + book + publish snapshots for the chosen symbols.
// Strategy thread: receive the snapshots, check sequence numbers, and record
// how long each update took to cross the ring (publish -> receive, measured
// with the TSC on two different cores).
//
// The file is replayed as fast as the feed thread can go, much faster than
// real time, so the ring sees bursts no live feed would produce. Stage 3
// replays at real speed over UDP.

#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <memory>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/common/latency_recorder.hpp"
#include "hft/common/mapped_file.hpp"
#include "hft/feed/feed_handler.hpp"
#include "hft/feed/measuring_consumer.hpp"
#include "hft/feed/pipeline.hpp"
#include "hft/strategy/model_strategy.hpp"

namespace {

using hft::feed::BookUpdate;

bool parse_int(std::string_view s, int& out) {
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

bool parse_size(std::string_view s, std::size_t& out) {
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

int usage() {
  std::fprintf(stderr,
               "usage: pipeline FILE --symbols SYM[,SYM...] [--feed-cpu N] [--strategy-cpu N] "
               "[--wait] [--max-orders N] [--model PATH] [--threshold LOGIT]\n");
  return 2;
}

std::string top_of_book(const BookUpdate& u) {
  char buf[96];
  if (u.bid_depth == 0 || u.ask_depth == 0) return "(one side empty)";
  std::snprintf(buf, sizeof buf, "%u x %u.%04u  /  %u.%04u x %u", u.bids[0].qty, u.bids[0].price / 10'000,
                u.bids[0].price % 10'000, u.asks[0].price / 10'000, u.asks[0].price % 10'000, u.asks[0].qty);
  return buf;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string path = argv[1];
  std::vector<std::string> symbols;
  hft::feed::FeedHandlerConfig cfg{.book = {.max_orders = std::size_t{4} << 20, .levels_per_side = 64},
                                   .on_full = hft::feed::OnFull::Drop};
  hft::feed::PipelineConfig pcfg{.feed_cpu = 2, .strategy_cpu = 3};
  std::string model_path;
  float threshold = 1.0f;  // |logit| > 1 means p > 0.73 or p < 0.27

  for (int i = 2; i < argc; ++i) {
    const std::string_view flag = argv[i];
    if (flag == "--wait") {
      cfg.on_full = hft::feed::OnFull::Wait;
      continue;
    }
    if (i + 1 >= argc) return usage();
    const std::string_view value = argv[++i];
    bool ok = true;
    if (flag == "--symbols") {
      std::size_t start = 0;
      while (start <= value.size()) {
        const std::size_t comma = value.find(',', start);
        const auto end = comma == std::string_view::npos ? value.size() : comma;
        if (end > start) symbols.emplace_back(value.substr(start, end - start));
        start = end + 1;
      }
    } else if (flag == "--feed-cpu") {
      ok = parse_int(value, pcfg.feed_cpu);
    } else if (flag == "--strategy-cpu") {
      ok = parse_int(value, pcfg.strategy_cpu);
    } else if (flag == "--max-orders") {
      ok = parse_size(value, cfg.book.max_orders);
    } else if (flag == "--model") {
      model_path = value;
    } else if (flag == "--threshold") {
      const auto [ptr, ec] = std::from_chars(value.data(), value.data() + value.size(), threshold);
      ok = ec == std::errc{} && ptr == value.data() + value.size();
    } else {
      ok = false;
    }
    if (!ok) return usage();
  }
  if (symbols.empty()) return usage();

  try {
    const hft::MappedFile file(path);
    std::printf("calibrating TSC... ");
    std::fflush(stdout);
    const auto tsc = hft::TscClock::calibrate();
    std::printf("%.4f ticks/ns\n", tsc.ticks_per_ns());

    // Everything the threads touch is allocated here, before they start.
    auto ring = std::make_unique<hft::feed::UpdateRing>();
    auto handler = std::make_unique<hft::feed::FeedHandler>(cfg, *ring);
    for (const auto& s : symbols) handler->subscribe_ticker(s);
    hft::LatencyRecorder latency(std::size_t{8} << 20);

    auto print_common = [&](const hft::feed::PipelineResult& result, double secs) {
      const auto& pub = handler->stats();
      std::printf("threads         feed on cpu %d (%s), strategy on cpu %d (%s)\n", pcfg.feed_cpu,
                  result.feed_pinned ? "pinned" : "NOT pinned", pcfg.strategy_cpu,
                  result.strategy_pinned ? "pinned" : "NOT pinned");
      std::printf("feed            %llu messages in %.3f s: %.1f ns/msg, %.1f M msg/s\n",
                  static_cast<unsigned long long>(result.feed.messages), secs,
                  secs * 1e9 / static_cast<double>(result.feed.messages),
                  static_cast<double>(result.feed.messages) / secs / 1e6);
      std::printf("updates         published %llu  unchanged %llu  dropped %llu  (ring full policy: %s)\n",
                  static_cast<unsigned long long>(pub.published), static_cast<unsigned long long>(pub.unchanged),
                  static_cast<unsigned long long>(pub.dropped),
                  cfg.on_full == hft::feed::OnFull::Drop ? "drop" : "wait");
    };

    if (!model_path.empty()) {
      // Stage 4: features -> model -> decision on the strategy thread.
      const auto model = hft::strategy::DefaultModel::load(model_path);
      hft::LatencyRecorder compute(std::size_t{8} << 20);
      hft::strategy::ModelStrategy<> strat(model, compute, latency, threshold, symbols.size());
      const auto t0 = std::chrono::steady_clock::now();
      const auto result = hft::feed::run_pipeline(file.bytes(), *handler, *ring, strat, pcfg);
      const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
      print_common(result, secs);
      const auto c = compute.summarize(tsc);
      const auto d = latency.summarize(tsc);
      std::printf("strategy        updates %llu  scored %llu  buy signals %llu  sell signals %llu  (|logit| > %.2f)\n",
                  static_cast<unsigned long long>(strat.updates()), static_cast<unsigned long long>(strat.scored()),
                  static_cast<unsigned long long>(strat.buy_signals()),
                  static_cast<unsigned long long>(strat.sell_signals()), static_cast<double>(threshold));
      std::printf("features+model  p50 %.0f ns  p90 %.0f  p99 %.0f  p99.9 %.0f  max %.0f\n", c.p50_ns, c.p90_ns,
                  c.p99_ns, c.p999_ns, c.max_ns);
      std::printf("publish->decide p50 %.0f ns  p90 %.0f  p99 %.0f  p99.9 %.0f  max %.0f  (ring hop + features + model)\n",
                  d.p50_ns, d.p90_ns, d.p99_ns, d.p999_ns, d.max_ns);
      return 0;
    }

    hft::feed::MeasuringConsumer strategy{.latency = latency, .latest = {}};
    strategy.latest.reserve(symbols.size());
    const auto t0 = std::chrono::steady_clock::now();
    const auto result = hft::feed::run_pipeline(file.bytes(), *handler, *ring, strategy, pcfg);
    const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    print_common(result, secs);
    const auto lat = latency.summarize(tsc);
    std::printf("strategy        received %llu  sequence gaps %llu  clock skew %llu\n",
                static_cast<unsigned long long>(strategy.received), static_cast<unsigned long long>(strategy.gaps),
                static_cast<unsigned long long>(strategy.clock_skew));
    std::printf("ring hop (ns)   p50 %.0f  p90 %.0f  p99 %.0f  p99.9 %.0f  max %.0f  (%zu samples)\n",
                lat.p50_ns, lat.p90_ns, lat.p99_ns, lat.p999_ns, lat.max_ns, lat.count);

    for (const auto& s : symbols) {
      const auto loc = handler->book().find_locate(s);
      if (!loc) {
        std::printf("%-8s not in the stock directory\n", s.c_str());
        continue;
      }
      const BookUpdate truth = handler->snapshot(*loc);
      const BookUpdate* seen = strategy.find(*loc);
      const bool match = seen != nullptr && hft::feed::same_levels(*seen, truth);
      std::printf("%-8s book %s   strategy's view %s\n", s.c_str(), top_of_book(truth).c_str(),
                  match ? "matches" : "differs (last update dropped)");
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "pipeline: %s\n", e.what());
    return 1;
  }
  return 0;
}
