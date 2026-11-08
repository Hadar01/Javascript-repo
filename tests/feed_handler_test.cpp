#include "hft/feed/feed_handler.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <vector>

namespace {

using namespace hft::itch;
using hft::Locate;
using hft::Side;
using hft::feed::BookUpdate;
using hft::feed::FeedHandler;
using hft::feed::UpdateRing;

constexpr Locate kA = 1;
constexpr Locate kB = 2;

Header hdr(Locate locate, hft::Timestamp ts = 1) { return Header{.locate = locate, .tracking = 0, .timestamp = ts}; }

AddOrder add(hft::OrderRef ref, Side side, hft::Price price, hft::Qty shares, Locate locate = kA) {
  return AddOrder{.hdr = hdr(locate), .order_ref = ref, .side = side, .shares = shares, .price = price};
}

// Single-threaded: the test is both the producer (through the handler) and
// the consumer (drain). That is allowed: an SPSC ring needs at most one
// thread on each end, and here they are the same thread.
class FeedHandlerTest : public ::testing::Test {
 protected:
  std::unique_ptr<UpdateRing> ring = std::make_unique<UpdateRing>();
  std::unique_ptr<FeedHandler> fh =
      std::make_unique<FeedHandler>(hft::feed::FeedHandlerConfig{.book = {.max_orders = 16'384, .levels_per_side = 16}}, *ring);

  std::vector<BookUpdate> drain() {
    std::vector<BookUpdate> out;
    BookUpdate u{};
    while (ring->try_pop(u)) out.push_back(u);
    return out;
  }
};

TEST_F(FeedHandlerTest, OnlySubscribedSymbolsArePublished) {
  fh->subscribe_locate(kA);
  fh->on(add(1, Side::Buy, 100, 10, kA));
  fh->on(add(2, Side::Buy, 100, 10, kB));
  const auto got = drain();
  ASSERT_EQ(got.size(), 1u);
  EXPECT_EQ(got[0].locate, kA);
  // Both books were still updated.
  EXPECT_TRUE(fh->book().book(kB).best(Side::Buy).has_value());
}

TEST_F(FeedHandlerTest, TickerSubscriptionResolvesAtStockDirectory) {
  fh->subscribe_ticker("AAPL");
  fh->subscribe_ticker("NOPE");  // never announced: no effect
  fh->on(StockDirectory{.hdr = hdr(7), .stock = {'A', 'A', 'P', 'L', ' ', ' ', ' ', ' '}});
  fh->on(add(1, Side::Sell, 200, 5, 7));
  fh->on(add(2, Side::Sell, 200, 5, 8));
  const auto got = drain();
  ASSERT_EQ(got.size(), 1u);
  EXPECT_EQ(got[0].locate, 7);
}

TEST_F(FeedHandlerTest, SnapshotHoldsTopLevelsBestFirst) {
  fh->subscribe_locate(kA);
  for (hft::OrderRef i = 0; i < 7; ++i) fh->on(add(i + 1, Side::Buy, static_cast<hft::Price>(100 + i), 10));
  fh->on(add(100, Side::Sell, 120, 3));
  fh->on(add(101, Side::Sell, 121, 4));
  const auto got = drain();
  ASSERT_FALSE(got.empty());
  const BookUpdate& u = got.back();
  EXPECT_EQ(u.bid_depth, 5);
  EXPECT_EQ(u.bids[0].price, 106u);  // best bid first
  EXPECT_EQ(u.bids[4].price, 102u);  // 5th level; levels 101 and 100 don't fit
  EXPECT_EQ(u.ask_depth, 2);
  EXPECT_EQ(u.asks[0], (BookUpdate::Level{.price = 120, .qty = 3}));
  EXPECT_EQ(u.asks[1], (BookUpdate::Level{.price = 121, .qty = 4}));
  EXPECT_EQ(u.asks[2], (BookUpdate::Level{.price = 0, .qty = 0}));  // unused entries are zero
}

TEST_F(FeedHandlerTest, ChangesBelowTheTopLevelsAreNotSent) {
  fh->subscribe_locate(kA);
  for (hft::OrderRef i = 0; i < 5; ++i) fh->on(add(i + 1, Side::Buy, static_cast<hft::Price>(100 + i), 10));
  EXPECT_EQ(drain().size(), 5u);

  fh->on(add(50, Side::Buy, 50, 10));  // 6th level: invisible in a 5-level snapshot
  EXPECT_TRUE(drain().empty());
  EXPECT_EQ(fh->stats().unchanged, 1u);

  fh->on(add(51, Side::Buy, 104, 1));  // best level grows: must be sent
  const auto got = drain();
  ASSERT_EQ(got.size(), 1u);
  EXPECT_EQ(got[0].bids[0].qty, 11u);
}

TEST_F(FeedHandlerTest, FullRingDropsAndSequenceShowsTheGap) {
  fh->subscribe_locate(kA);
  // Each add changes the best bid, so each one is published. No consumer
  // runs, so the ring fills after UpdateRing::kCapacity updates.
  const auto n = static_cast<hft::OrderRef>(UpdateRing::kCapacity);
  for (hft::OrderRef i = 0; i <= n; ++i) fh->on(add(i + 1, Side::Buy, static_cast<hft::Price>(1000 + i), 1));
  EXPECT_EQ(fh->stats().published, UpdateRing::kCapacity);
  EXPECT_EQ(fh->stats().dropped, 1u);

  auto got = drain();
  ASSERT_EQ(got.size(), UpdateRing::kCapacity);
  EXPECT_EQ(got.back().seq, n - 1);

  fh->on(add(n + 2, Side::Buy, static_cast<hft::Price>(1000 + n + 1), 1));
  got = drain();
  ASSERT_EQ(got.size(), 1u);
  EXPECT_EQ(got[0].seq, n + 1);  // seq n was the dropped update: the consumer sees a gap of one
}

// After a drop, the next comparison must be against what the strategy
// actually HAS, not against the update that was dropped. Otherwise a book
// that stops changing would never be resent and the strategy would stay
// stale.
TEST_F(FeedHandlerTest, AfterADropTheBookIsResentEvenIfItDidNotChangeAgain) {
  fh->subscribe_locate(kA);
  const auto n = static_cast<hft::OrderRef>(UpdateRing::kCapacity);
  for (hft::OrderRef i = 0; i < n; ++i) fh->on(add(i + 1, Side::Buy, static_cast<hft::Price>(1000 + i), 1));
  const BookUpdate delivered_last = fh->snapshot(kA);

  fh->on(add(n + 1, Side::Sell, 5000, 7));  // state S1: dropped, ring full
  EXPECT_EQ(fh->stats().dropped, 1u);
  drain();

  fh->on(add(n + 2, Side::Buy, 1, 1));  // deep bid: the top 5 levels still equal S1
  const auto got = drain();
  ASSERT_EQ(got.size(), 1u) << "S1 must be resent: the strategy never received it";
  EXPECT_FALSE(hft::feed::same_levels(got[0], delivered_last));
  EXPECT_EQ(got[0].asks[0], (BookUpdate::Level{.price = 5000, .qty = 7}));
}

TEST_F(FeedHandlerTest, HugeLevelsSaturateInsteadOfWrapping) {
  fh->subscribe_locate(kA);
  fh->on(add(1, Side::Sell, 10, 3'000'000'000u));
  fh->on(add(2, Side::Sell, 10, 3'000'000'000u));  // 6e9 shares at one level
  const auto got = drain();
  ASSERT_EQ(got.size(), 2u);
  EXPECT_EQ(got.back().asks[0].qty, 4'294'967'295u);
}

}  // namespace
