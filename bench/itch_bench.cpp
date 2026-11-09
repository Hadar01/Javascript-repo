// Parser and order book throughput on synthetic ITCH feeds.
//
// Two working-set sizes, because the answer depends on which cache the data
// fits in:
//   small: 4k live orders. The order table is ~400 KB and fits in L2.
//   large: 500k live orders. The table is ~48 MB, bigger than this machine's
//          L3, so most lookups go to DRAM. Real Nasdaq data looks like this.
//
// Each run processes a whole feed; ns_per_msg is the mean cost per message.
// Per-message percentiles (p50/p99) come in stage 5 with rdtsc timestamps.

#include <benchmark/benchmark.h>

#include <cstdint>
#include <memory>
#include <vector>

#include "hft/book/market_book.hpp"
#include "hft/itch/parser.hpp"
#include "hft/itch/synthetic.hpp"
#include "reference_book.hpp"

namespace {

using hft::itch::SyntheticFeedConfig;

struct Workload {
  SyntheticFeedConfig feed_cfg;
  std::size_t max_orders;
};

const Workload kSmall{{.symbols = 8, .messages = 2'000'000, .target_live_orders = 4'000, .max_level_offset = 32, .seed = 1},
                      8'192};
const Workload kLarge{{.symbols = 64, .messages = 8'000'000, .target_live_orders = 500'000, .max_level_offset = 32, .seed = 2},
                      1'000'000};

// Generated once per process; generation is not part of any measurement.
const std::vector<std::byte>& feed_for(const Workload& w) {
  if (&w == &kSmall) {
    static const auto f = hft::itch::make_synthetic_feed(w.feed_cfg);
    return f;
  }
  static const auto f = hft::itch::make_synthetic_feed(w.feed_cfg);
  return f;
}

void set_counters(benchmark::State& state, std::uint64_t messages_per_iteration) {
  // kIsIterationInvariantRate: messages * iterations / elapsed seconds.
  // kInvert turns that into seconds per message (printed with an SI prefix:
  // "25n" = 25 ns).
  state.counters["per_msg"] = benchmark::Counter(static_cast<double>(messages_per_iteration),
                                                 benchmark::Counter::kIsIterationInvariantRate |
                                                     benchmark::Counter::kInvert);
}

// Uses the header of every message, so the parser must at least frame,
// dispatch and decode headers. Fields it doesn't read may be skipped by the
// optimiser, as they would be for any real handler.
struct Checksum {
  std::uint64_t sum = 0;
  template <typename M>
  void on(const M& m) {
    sum += m.hdr.timestamp ^ m.hdr.locate;
  }
};

void BM_ParseOnly(benchmark::State& state, const Workload& w) {
  const auto& feed = feed_for(w);
  std::uint64_t messages = 0;
  for (auto _ : state) {
    Checksum h;
    const auto stats = hft::itch::parse_binary_file(feed, h);
    benchmark::DoNotOptimize(h.sum);
    messages = stats.messages;
  }
  set_counters(state, messages);
}

template <typename Book>
std::unique_ptr<Book> make_book(const Workload& w) {
  if constexpr (std::is_same_v<Book, hft::book::MarketBook>) {
    return std::make_unique<Book>(hft::book::MarketBookConfig{.max_orders = w.max_orders, .levels_per_side = 64});
  } else {
    return std::make_unique<Book>();
  }
}

// A fresh book per iteration: replaying the same feed into a used book
// would make every add a duplicate. Building and destroying the book is
// excluded from the timing with PauseTiming.
template <typename Book>
void BM_ParseAndBook(benchmark::State& state, const Workload& w) {
  const auto& feed = feed_for(w);
  std::uint64_t messages = 0;
  for (auto _ : state) {
    state.PauseTiming();
    auto book = make_book<Book>(w);
    state.ResumeTiming();

    const auto stats = hft::itch::parse_binary_file(feed, *book);
    benchmark::DoNotOptimize(book->live_orders());
    messages = stats.messages;

    state.PauseTiming();
    book.reset();
    state.ResumeTiming();
  }
  set_counters(state, messages);
}

using hft::book::MarketBook;
using hft::testing::ReferenceBook;

BENCHMARK_CAPTURE(BM_ParseOnly, small, kSmall)->Unit(benchmark::kMillisecond);
BENCHMARK_CAPTURE(BM_ParseOnly, large, kLarge)->Unit(benchmark::kMillisecond);
BENCHMARK_CAPTURE(BM_ParseAndBook<MarketBook>, small, kSmall)->Unit(benchmark::kMillisecond);
BENCHMARK_CAPTURE(BM_ParseAndBook<MarketBook>, large, kLarge)->Unit(benchmark::kMillisecond);
BENCHMARK_CAPTURE(BM_ParseAndBook<ReferenceBook>, small, kSmall)->Unit(benchmark::kMillisecond);
BENCHMARK_CAPTURE(BM_ParseAndBook<ReferenceBook>, large, kLarge)->Unit(benchmark::kMillisecond);

}  // namespace
