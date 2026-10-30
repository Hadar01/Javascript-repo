#include "hft/book/order_book.hpp"

#include <gtest/gtest.h>

#include <vector>

namespace {

using hft::Price;
using hft::Side;
using hft::book::Level;
using hft::book::OrderBook;

std::vector<Price> prices(const OrderBook& b, Side side) {
  std::vector<Price> out;
  for (std::size_t d = 0; d < b.depth(side); ++d) out.push_back(b.level(side, d)->price);
  return out;
}

TEST(OrderBook, EmptyBook) {
  OrderBook b;
  EXPECT_FALSE(b.best(Side::Buy).has_value());
  EXPECT_FALSE(b.best(Side::Sell).has_value());
  EXPECT_EQ(b.depth(Side::Buy), 0u);
}

TEST(OrderBook, BidsAreHighestFirstAsksLowestFirst) {
  OrderBook b;
  for (Price p : {100u, 103u, 101u, 102u}) b.add(Side::Buy, p, 10);
  for (Price p : {110u, 107u, 109u, 108u}) b.add(Side::Sell, p, 10);
  EXPECT_EQ(prices(b, Side::Buy), (std::vector<Price>{103, 102, 101, 100}));
  EXPECT_EQ(prices(b, Side::Sell), (std::vector<Price>{107, 108, 109, 110}));
  EXPECT_EQ(b.best(Side::Buy)->price, 103u);
  EXPECT_EQ(b.best(Side::Sell)->price, 107u);
}

TEST(OrderBook, SamePriceAggregates) {
  OrderBook b;
  b.add(Side::Buy, 100, 10);
  b.add(Side::Buy, 100, 25);
  EXPECT_EQ(b.depth(Side::Buy), 1u);
  EXPECT_EQ(*b.best(Side::Buy), (Level{.price = 100, .order_count = 2, .qty = 35}));
}

TEST(OrderBook, PartialReduceKeepsLevelAndCount) {
  OrderBook b;
  b.add(Side::Sell, 200, 50);
  EXPECT_TRUE(b.reduce(Side::Sell, 200, 20, /*order_gone=*/false));
  EXPECT_EQ(*b.best(Side::Sell), (Level{.price = 200, .order_count = 1, .qty = 30}));
}

TEST(OrderBook, LevelDisappearsWithItsLastOrder) {
  OrderBook b;
  b.add(Side::Buy, 100, 10);
  b.add(Side::Buy, 100, 20);
  b.add(Side::Buy, 99, 5);
  EXPECT_TRUE(b.reduce(Side::Buy, 100, 10, true));
  EXPECT_EQ(*b.best(Side::Buy), (Level{.price = 100, .order_count = 1, .qty = 20}));
  EXPECT_TRUE(b.reduce(Side::Buy, 100, 20, true));
  EXPECT_EQ(b.best(Side::Buy)->price, 99u);
  EXPECT_EQ(b.depth(Side::Buy), 1u);
}

TEST(OrderBook, ReduceUnknownPriceFails) {
  OrderBook b;
  b.add(Side::Buy, 100, 10);
  EXPECT_FALSE(b.reduce(Side::Buy, 101, 10, true));
  EXPECT_FALSE(b.reduce(Side::Sell, 100, 10, true));  // right price, wrong side
  EXPECT_EQ(b.best(Side::Buy)->qty, 10u);
}

TEST(OrderBook, InsertAndEraseInTheMiddle) {
  OrderBook b;
  for (Price p : {100u, 102u, 104u}) b.add(Side::Sell, p, 1);
  b.add(Side::Sell, 103, 1);
  EXPECT_EQ(prices(b, Side::Sell), (std::vector<Price>{100, 102, 103, 104}));
  b.reduce(Side::Sell, 102, 1, true);
  EXPECT_EQ(prices(b, Side::Sell), (std::vector<Price>{100, 103, 104}));
}

TEST(OrderBook, LevelBeyondDepthIsEmpty) {
  OrderBook b;
  b.add(Side::Buy, 100, 1);
  EXPECT_TRUE(b.level(Side::Buy, 0).has_value());
  EXPECT_FALSE(b.level(Side::Buy, 1).has_value());
}

TEST(OrderBook, CountsGrowthBeyondReserve) {
  OrderBook b;
  b.reserve(4);
  for (Price p = 1; p <= 4; ++p) b.add(Side::Buy, p, 1);
  EXPECT_EQ(b.growth_events(), 0u);
  b.add(Side::Buy, 5, 1);  // a fifth level does not fit
  EXPECT_EQ(b.growth_events(), 1u);
  b.add(Side::Buy, 5, 1);  // same level: no new element, no growth
  EXPECT_EQ(b.growth_events(), 1u);
}

}  // namespace
