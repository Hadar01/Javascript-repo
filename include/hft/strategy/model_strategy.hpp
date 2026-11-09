#pragma once

// ModelStrategy: the strategy thread's consumer from stage 4 on.
//
// For every BookUpdate: features -> model -> decision. It doesn't send
// orders (no exchange here); a decision counts as a buy or sell signal when
// the model is confident, i.e. |logit| exceeds a threshold. It records:
//   compute latency:  features + model, on this thread alone
//   decision latency: from the feed thread's publish to the decision, which
//                     adds the ring hop (TSC on two cores)
// It doesn't allocate after setup: one FeatureBuilder per symbol, reserved
// up front, and fixed-size arrays everywhere else.

#include <cstdint>
#include <utility>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/common/latency_recorder.hpp"
#include "hft/features/features.hpp"
#include "hft/feed/book_update.hpp"
#include "hft/model/mlp.hpp"

namespace hft::strategy {

// The architecture trained by python/train.py: 10 features -> 32 -> 16 -> 1.
using DefaultModel = model::Mlp<features::kNumFeatures, 32, 16>;

template <typename Model = DefaultModel>
class ModelStrategy {
 public:
  ModelStrategy(const Model& model, LatencyRecorder& compute_latency, LatencyRecorder& decision_latency,
                float threshold_logit, std::size_t max_symbols)
      : model_(model),
        compute_latency_(compute_latency),
        decision_latency_(decision_latency),
        threshold_(threshold_logit) {
    builders_.reserve(max_symbols);
  }

  void operator()(const feed::BookUpdate& u) noexcept {
    const std::uint64_t t0 = rdtsc();
    if (u.seq != next_seq_) gaps_ += u.seq - next_seq_;
    next_seq_ = u.seq + 1;
    ++updates_;

    features::FeatureBuilder* fb = builder_for(u.locate);
    features::FeatureVector x;
    if (fb == nullptr || !fb->update(u, x)) return;  // unknown symbol, or one-sided book

    const float logit = model_.logit(x);
    if (logit > threshold_) {
      ++buy_signals_;
    } else if (logit < -threshold_) {
      ++sell_signals_;
    }
    ++scored_;

    const std::uint64_t t1 = rdtsc();
    compute_latency_.record(t1 - t0);
    if (t1 >= u.publish_tsc) decision_latency_.record(t1 - u.publish_tsc);
  }

  [[nodiscard]] std::uint64_t updates() const noexcept { return updates_; }
  [[nodiscard]] std::uint64_t scored() const noexcept { return scored_; }
  [[nodiscard]] std::uint64_t buy_signals() const noexcept { return buy_signals_; }
  [[nodiscard]] std::uint64_t sell_signals() const noexcept { return sell_signals_; }
  [[nodiscard]] std::uint64_t gaps() const noexcept { return gaps_; }

 private:
  // A handful of symbols: a linear search over a contiguous vector beats a
  // hash map at this size. Returns nullptr when more symbols show up than
  // were reserved, rather than allocating on the hot path.
  features::FeatureBuilder* builder_for(Locate locate) noexcept {
    for (auto& [loc, fb] : builders_) {
      if (loc == locate) return &fb;
    }
    if (builders_.size() == builders_.capacity()) return nullptr;
    builders_.emplace_back(locate, features::FeatureBuilder{});
    return &builders_.back().second;
  }

  const Model& model_;
  LatencyRecorder& compute_latency_;
  LatencyRecorder& decision_latency_;
  float threshold_;
  std::vector<std::pair<Locate, features::FeatureBuilder>> builders_;
  std::uint64_t updates_ = 0, scored_ = 0, buy_signals_ = 0, sell_signals_ = 0, gaps_ = 0, next_seq_ = 0;
};

}  // namespace hft::strategy
