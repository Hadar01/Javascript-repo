// Stage 4 costs on the strategy thread: features, model, and the whole
// per-update step. The model and its inputs are the ones python/train.py
// exported (tests/data). Inputs cycle through 1,000 real test rows, so the
// compiler can't precompute anything.

#include <benchmark/benchmark.h>

#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "hft/common/latency_recorder.hpp"
#include "hft/features/features.hpp"
#include "hft/feed/book_update.hpp"
#include "hft/strategy/model_strategy.hpp"

namespace {

using hft::features::FeatureVector;
using hft::feed::BookUpdate;
using hft::strategy::DefaultModel;

const std::string kDataDir = HFT_TEST_DATA_DIR;

const DefaultModel& model() {
  static const DefaultModel m = DefaultModel::load(kDataDir + "/model.bin");
  return m;
}

const std::vector<FeatureVector>& inputs() {
  static const std::vector<FeatureVector> x = [] {
    std::ifstream f(kDataDir + "/golden.bin", std::ios::binary);
    char magic[8];
    std::uint32_t dims[2];
    f.read(magic, 8);
    f.read(reinterpret_cast<char*>(dims), sizeof dims);
    if (!f) throw std::runtime_error("cannot read golden.bin");
    std::vector<FeatureVector> v(dims[1]);
    f.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(v.size() * sizeof(FeatureVector)));
    return v;
  }();
  return x;
}

// 1,024 two-sided books whose prices and sizes wander, so every feature
// (including the flow ones) does real work.
const std::vector<BookUpdate>& books() {
  static const std::vector<BookUpdate> v = [] {
    std::vector<BookUpdate> out(1024);
    std::uint64_t r = 12345;
    hft::Price bid = 1'000'000;
    for (std::size_t i = 0; i < out.size(); ++i) {
      r = r * 6364136223846793005ULL + 1442695040888963407ULL;
      const std::int64_t step = static_cast<std::int64_t>(r >> 62) - 1;  // -1, 0, +1 or +2 ticks
      bid = static_cast<hft::Price>(static_cast<std::int64_t>(bid) + 100 * step);
      BookUpdate& u = out[i];
      u.locate = 1;
      u.exch_ts = 1'000'000 + 1'000 * i;
      u.bid_depth = u.ask_depth = 5;
      for (std::uint32_t d = 0; d < 5; ++d) {
        u.bids[d] = {.price = bid - 100 * d, .qty = static_cast<std::uint32_t>(100 + ((r >> (8 * d)) & 0x3FF))};
        u.asks[d] = {.price = bid + 200 + 100 * d, .qty = static_cast<std::uint32_t>(100 + ((r >> (8 * d + 4)) & 0x3FF))};
      }
    }
    return out;
  }();
  return v;
}

void BM_Features(benchmark::State& state) {
  hft::features::FeatureBuilder fb;
  const auto& b = books();
  FeatureVector x;
  std::size_t i = 0;
  for (auto _ : state) {
    benchmark::DoNotOptimize(fb.update(b[i++ & 1023], x));
    benchmark::DoNotOptimize(x);
  }
}
BENCHMARK(BM_Features);

void BM_ModelLogit(benchmark::State& state) {
  const auto& m = model();
  const auto& x = inputs();
  std::size_t i = 0;
  for (auto _ : state) {
    benchmark::DoNotOptimize(m.logit(x[i]));
    if (++i == x.size()) i = 0;
  }
}
BENCHMARK(BM_ModelLogit);

void BM_ModelProbability(benchmark::State& state) {
  const auto& m = model();
  const auto& x = inputs();
  std::size_t i = 0;
  for (auto _ : state) {
    benchmark::DoNotOptimize(m.probability(x[i]));
    if (++i == x.size()) i = 0;
  }
}
BENCHMARK(BM_ModelProbability);

// Everything the strategy thread does per update: sequence check, features,
// model, decision, and two rdtsc reads for its own latency stats.
void BM_StrategyStep(benchmark::State& state) {
  hft::LatencyRecorder compute(1 << 20), decision(1 << 20);
  hft::strategy::ModelStrategy<> strat(model(), compute, decision, 1.0f, 8);
  auto b = books();  // a copy: seq numbers are rewritten below
  std::uint64_t seq = 0;
  std::size_t i = 0;
  for (auto _ : state) {
    BookUpdate& u = b[i++ & 1023];
    u.seq = seq++;
    strat(u);
    // Use the decision. Without this, -O3 inlines everything, sees that the
    // buy/sell counters are never read, and deletes the model: the "whole
    // step" then measured 44 ns, faster than the model alone (measured).
    benchmark::DoNotOptimize(strat.buy_signals());
    benchmark::DoNotOptimize(strat.sell_signals());
  }
}
BENCHMARK(BM_StrategyStep);

}  // namespace
