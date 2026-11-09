#pragma once

// Order-book features, computed from the BookUpdate snapshots the strategy
// thread receives.
//
// This is the ONLY implementation of the features. Training data comes from
// apps/feature_dump, which runs the real pipeline and calls this same code,
// and Python trains on that file. If Python computed its own features, the
// two implementations would drift apart (rounding, edge cases, a changed
// window), and the model would see different numbers live than in
// training: "train/serve skew", a classic way for production ML to fail
// silently.
//
// FeatureBuilder keeps a little state per symbol (the previous snapshot and
// two moving averages), so the strategy needs one builder per symbol.
// Everything is fixed-size: no allocation.

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

#include "hft/feed/book_update.hpp"

namespace hft::features {

inline constexpr std::size_t kNumFeatures = 10;
using FeatureVector = std::array<float, kNumFeatures>;

// Order matters: it is the column order of the training data and the input
// order of the model. feature_dump writes these names next to the data.
inline constexpr std::array<const char*, kNumFeatures> kFeatureNames = {
    "spread_ticks",             // ask - bid, in ticks
    "imbalance_1",              // (bid qty - ask qty) / (bid qty + ask qty), best level
    "imbalance_3",              // same over the top 3 levels
    "imbalance_5",              // same over the top 5 levels
    "microprice_offset_ticks",  // size-weighted price minus mid, in ticks
    "ofi_1",                    // order-flow imbalance at the best level since the last update
    "ofi_ema",                  // its exponential moving average
    "last_move_sign",           // +1 / -1: direction of the most recent mid change
    "mid_dev_ticks",            // mid minus its moving average, in ticks
    "log_dt_us",                // log(1 + microseconds since this symbol's last update)
};

// One tick is $0.01, which is 100 in ITCH Price(4) units. (Stocks under $1
// trade in $0.0001 ticks; this project doesn't handle that case.)
inline constexpr double kTick = 100.0;

class FeatureBuilder {
 public:
  // Fills `out` and returns true for a two-sided book. A one-sided book has
  // no mid, so it gets no features and leaves the state untouched.
  bool update(const feed::BookUpdate& u, FeatureVector& out) noexcept {
    if (u.bid_depth == 0 || u.ask_depth == 0) return false;

    const double bid = u.bids[0].price;
    const double ask = u.asks[0].price;
    const double bq = u.bids[0].qty;
    const double aq = u.asks[0].qty;
    const double mid = 0.5 * (bid + ask);
    const double spread = ask - bid;
    // Zero only if the best levels hold zero-share orders (legal in ITCH).
    const double top = bq + aq > 0.0 ? bq + aq : 1.0;

    // Order-flow imbalance (Cont, Kukanov & Stoikov, 2014): how much
    // liquidity arrived on the bid minus how much arrived on the ask at
    // the best prices since the previous snapshot. A rising bid counts its
    // whole queue as new buying interest; a falling bid counts the old
    // queue as removed; an unchanged bid counts the change in size.
    double ofi = 0.0;
    double dt_us = 0.0;
    if (has_prev_) {
      const double e_bid = (bid >= prev_bid_ ? bq : 0.0) - (bid <= prev_bid_ ? prev_bq_ : 0.0);
      const double e_ask = (ask <= prev_ask_ ? aq : 0.0) - (ask >= prev_ask_ ? prev_aq_ : 0.0);
      // Divided by the current best-level depth, so the number means the
      // same thing for a thin stock as for a thick one.
      ofi = (e_bid - e_ask) / top;
      if (mid != prev_mid_) last_move_sign_ = mid > prev_mid_ ? 1.0 : -1.0;
      dt_us = u.exch_ts > prev_ts_ ? static_cast<double>(u.exch_ts - prev_ts_) / 1000.0 : 0.0;
      ofi_ema_ += kAlphaOfi * (ofi - ofi_ema_);
      mid_ema_ += kAlphaMid * (mid - mid_ema_);
    } else {
      mid_ema_ = mid;
    }

    const double imb1 = (bq - aq) / top;
    out[0] = static_cast<float>(spread / kTick);
    out[1] = static_cast<float>(imb1);
    out[2] = static_cast<float>(imbalance(u, 3));
    out[3] = static_cast<float>(imbalance(u, 5));
    // Microprice = (bid*aq + ask*bq) / (aq + bq): the mid, tilted toward the
    // side with less liquidity (the side more likely to be consumed next).
    // Its offset from the mid simplifies to (spread / 2) * imbalance_1.
    out[4] = static_cast<float>(0.5 * spread * imb1 / kTick);
    out[5] = static_cast<float>(ofi);
    out[6] = static_cast<float>(ofi_ema_);
    out[7] = static_cast<float>(last_move_sign_);
    out[8] = static_cast<float>((mid - mid_ema_) / kTick);
    out[9] = static_cast<float>(std::log1p(dt_us));

    has_prev_ = true;
    prev_bid_ = bid;
    prev_ask_ = ask;
    prev_bq_ = bq;
    prev_aq_ = aq;
    prev_mid_ = mid;
    prev_ts_ = u.exch_ts;
    return true;
  }

 private:
  static constexpr double kAlphaOfi = 0.1;   // ~10-update memory
  static constexpr double kAlphaMid = 0.05;  // ~20-update memory

  // (sum of bid qty - sum of ask qty) / total, over the top `levels` levels.
  static double imbalance(const feed::BookUpdate& u, std::size_t levels) noexcept {
    double b = 0.0, a = 0.0;
    for (std::size_t i = 0; i < levels && i < u.bid_depth; ++i) b += u.bids[i].qty;
    for (std::size_t i = 0; i < levels && i < u.ask_depth; ++i) a += u.asks[i].qty;
    return b + a > 0.0 ? (b - a) / (b + a) : 0.0;
  }

  bool has_prev_ = false;
  double prev_bid_ = 0, prev_ask_ = 0, prev_bq_ = 0, prev_aq_ = 0, prev_mid_ = 0;
  Timestamp prev_ts_ = 0;
  double ofi_ema_ = 0, mid_ema_ = 0, last_move_sign_ = 0;
};

}  // namespace hft::features
