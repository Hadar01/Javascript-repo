#include "hft/features/features.hpp"

#include <gtest/gtest.h>

#include <cmath>

namespace {

using hft::feed::BookUpdate;
using hft::features::FeatureBuilder;
using hft::features::FeatureVector;

enum F { kSpread, kImb1, kImb3, kImb5, kMicro, kOfi, kOfiEma, kLastMove, kMidDev, kLogDt };

// A book with up to 5 levels per side given as {price, qty} pairs, best first.
BookUpdate book(std::initializer_list<BookUpdate::Level> bids, std::initializer_list<BookUpdate::Level> asks,
                hft::Timestamp ts = 1'000'000) {
  BookUpdate u{};
  u.locate = 1;
  u.exch_ts = ts;
  for (const auto& l : bids) u.bids[u.bid_depth++] = l;
  for (const auto& l : asks) u.asks[u.ask_depth++] = l;
  return u;
}

TEST(Features, OneSidedBookHasNoFeatures) {
  FeatureBuilder fb;
  FeatureVector x{};
  EXPECT_FALSE(fb.update(book({{10000, 5}}, {}), x));
  EXPECT_FALSE(fb.update(book({}, {{10100, 5}}), x));
}

TEST(Features, SnapshotFeatures) {
  FeatureBuilder fb;
  FeatureVector x{};
  // Best bid $1.00 x 300, best ask $1.02 x 100: spread 2 ticks.
  ASSERT_TRUE(fb.update(book({{10000, 300}, {9900, 100}, {9800, 100}, {9700, 500}},
                             {{10200, 100}, {10300, 100}, {10400, 400}}),
                        x));
  EXPECT_FLOAT_EQ(x[kSpread], 2.0f);
  EXPECT_FLOAT_EQ(x[kImb1], (300.0f - 100) / 400);                 // 0.5
  EXPECT_FLOAT_EQ(x[kImb3], (500.0f - 600) / 1100);                // top 3 levels
  EXPECT_FLOAT_EQ(x[kImb5], (1000.0f - 600) / 1600);               // all levels present
  EXPECT_FLOAT_EQ(x[kMicro], 0.5f * 2 * 0.5f);                     // spread/2 * imbalance_1, ticks
  // First update: nothing to compare with yet.
  EXPECT_FLOAT_EQ(x[kOfi], 0.0f);
  EXPECT_FLOAT_EQ(x[kLastMove], 0.0f);
  EXPECT_FLOAT_EQ(x[kMidDev], 0.0f);
  EXPECT_FLOAT_EQ(x[kLogDt], 0.0f);
}

TEST(Features, MicropriceLeansTowardTheThinSide) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 100}}, {{10200, 300}}), x));  // thin bid
  EXPECT_LT(x[kMicro], 0.0f);  // microprice below the mid: the bid is more likely to go
}

// Order-flow imbalance, one case of the formula per test.
TEST(Features, OfiSamePricesCountsSizeChanges) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 100}}, {{10200, 100}}), x));
  ASSERT_TRUE(fb.update(book({{10000, 160}}, {{10200, 80}}), x));
  // e_bid = 160 - 100 = +60, e_ask = 80 - 100 = -20, ofi = (60 - -20) / (160 + 80)
  EXPECT_FLOAT_EQ(x[kOfi], 80.0f / 240);
}

TEST(Features, OfiRisingBidCountsTheWholeNewQueue) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 100}}, {{10200, 100}}), x));
  ASSERT_TRUE(fb.update(book({{10100, 50}}, {{10200, 100}}), x));
  // Bid up: e_bid = +50 (new queue). Ask unchanged with the same size: 0.
  EXPECT_FLOAT_EQ(x[kOfi], 50.0f / 150);
  EXPECT_FLOAT_EQ(x[kLastMove], 1.0f);  // mid rose
}

TEST(Features, OfiFallingBidCountsTheOldQueueAsRemoved) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 100}}, {{10200, 100}}), x));
  ASSERT_TRUE(fb.update(book({{9900, 70}}, {{10200, 100}}), x));
  // Bid down: e_bid = -100 (old queue gone).
  EXPECT_FLOAT_EQ(x[kOfi], -100.0f / 170);
  EXPECT_FLOAT_EQ(x[kLastMove], -1.0f);
}

TEST(Features, LastMoveSignPersistsUntilTheMidMovesAgain) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 100}}, {{10200, 100}}), x));
  ASSERT_TRUE(fb.update(book({{10100, 100}}, {{10200, 100}}), x));  // up
  ASSERT_TRUE(fb.update(book({{10100, 300}}, {{10200, 100}}), x));  // size change only
  EXPECT_FLOAT_EQ(x[kLastMove], 1.0f);
}

TEST(Features, TimeSinceLastUpdate) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 1}}, {{10200, 1}}, 1'000'000), x));
  ASSERT_TRUE(fb.update(book({{10000, 1}}, {{10200, 1}}, 1'000'000 + 9'000), x));  // 9 us later
  EXPECT_FLOAT_EQ(x[kLogDt], static_cast<float>(std::log1p(9.0)));
}

TEST(Features, ZeroSizedBestLevelsDoNotDivideByZero) {
  FeatureBuilder fb;
  FeatureVector x{};
  ASSERT_TRUE(fb.update(book({{10000, 0}}, {{10200, 0}}), x));
  for (float v : x) EXPECT_TRUE(std::isfinite(v));
}

}  // namespace
