#include "hft/book/market_book.hpp"

#include <gtest/gtest.h>

#include <vector>

#include "hft/itch/parser.hpp"
#include "hft/itch/synthetic.hpp"
#include "reference_book.hpp"

namespace {

using namespace hft::itch;
using hft::Locate;
using hft::Side;
using hft::book::Level;
using hft::book::MarketBook;

constexpr Locate kAapl = 5;
Header hdr(Locate locate = kAapl) { return Header{.locate = locate, .tracking = 0, .timestamp = 1}; }

AddOrder add(hft::OrderRef ref, Side side, hft::Price price, hft::Qty shares, Locate locate = kAapl) {
  return AddOrder{.hdr = hdr(locate), .order_ref = ref, .side = side, .shares = shares, .price = price};
}

class MarketBookTest : public ::testing::Test {
 protected:
  MarketBook mb{{.max_orders = 1024, .levels_per_side = 16}};
  const hft::book::OrderBook& aapl() const { return mb.book(kAapl); }
};

TEST_F(MarketBookTest, StockDirectoryNamesTheLocate) {
  mb.on(StockDirectory{.hdr = hdr(), .stock = {'A', 'A', 'P', 'L', ' ', ' ', ' ', ' '}});
  EXPECT_EQ(mb.symbol(kAapl), "AAPL");
  EXPECT_EQ(mb.find_locate("AAPL"), kAapl);
  EXPECT_FALSE(mb.find_locate("MSFT").has_value());
  EXPECT_EQ(mb.symbol(kAapl + 1), "");
}

TEST_F(MarketBookTest, AddBuildsBothSides) {
  mb.on(add(1, Side::Buy, 1'000'000, 100));
  mb.on(add(2, Side::Buy, 999'900, 200));
  mb.on(add(3, Side::Sell, 1'000'100, 300));
  EXPECT_EQ(*aapl().best(Side::Buy), (Level{.price = 1'000'000, .order_count = 1, .qty = 100}));
  EXPECT_EQ(aapl().level(Side::Buy, 1)->price, 999'900u);
  EXPECT_EQ(*aapl().best(Side::Sell), (Level{.price = 1'000'100, .order_count = 1, .qty = 300}));
  EXPECT_EQ(mb.live_orders(), 3u);
}

TEST_F(MarketBookTest, SymbolsAreIndependent) {
  mb.on(add(1, Side::Buy, 100, 10, kAapl));
  mb.on(add(2, Side::Buy, 200, 20, kAapl + 1));
  EXPECT_EQ(mb.book(kAapl).best(Side::Buy)->price, 100u);
  EXPECT_EQ(mb.book(kAapl + 1).best(Side::Buy)->price, 200u);
}

TEST_F(MarketBookTest, PartialExecutionThenFullExecution) {
  mb.on(add(1, Side::Sell, 500, 100));
  mb.on(OrderExecuted{.hdr = hdr(), .order_ref = 1, .executed_shares = 40, .match_number = 1});
  EXPECT_EQ(aapl().best(Side::Sell)->qty, 60u);
  EXPECT_EQ(mb.live_orders(), 1u);
  mb.on(OrderExecutedWithPrice{.hdr = hdr(), .order_ref = 1, .executed_shares = 60, .match_number = 2,
                               .printable = 'Y', .execution_price = 499});
  EXPECT_FALSE(aapl().best(Side::Sell).has_value());
  EXPECT_EQ(mb.live_orders(), 0u);
}

TEST_F(MarketBookTest, CancelIsPartialDeleteIsFull) {
  mb.on(add(1, Side::Buy, 500, 100));
  mb.on(add(2, Side::Buy, 500, 50));
  mb.on(OrderCancel{.hdr = hdr(), .order_ref = 1, .cancelled_shares = 30});
  EXPECT_EQ(*aapl().best(Side::Buy), (Level{.price = 500, .order_count = 2, .qty = 120}));
  mb.on(OrderDelete{.hdr = hdr(), .order_ref = 1});
  EXPECT_EQ(*aapl().best(Side::Buy), (Level{.price = 500, .order_count = 1, .qty = 50}));
}

TEST_F(MarketBookTest, ReplaceMovesOrderKeepingSide) {
  mb.on(add(1, Side::Sell, 500, 100));
  mb.on(OrderReplace{.hdr = hdr(), .original_ref = 1, .new_ref = 2, .shares = 70, .price = 501});
  EXPECT_EQ(*aapl().best(Side::Sell), (Level{.price = 501, .order_count = 1, .qty = 70}));
  EXPECT_EQ(aapl().depth(Side::Sell), 1u);
  EXPECT_EQ(aapl().depth(Side::Buy), 0u);
  // The old reference is gone, the new one is live.
  mb.on(OrderDelete{.hdr = hdr(), .order_ref = 1});
  EXPECT_EQ(mb.stats().unknown_order, 1u);
  mb.on(OrderDelete{.hdr = hdr(), .order_ref = 2});
  EXPECT_EQ(mb.live_orders(), 0u);
}

TEST_F(MarketBookTest, AnomaliesAreCountedNotApplied) {
  mb.on(add(1, Side::Buy, 500, 100));

  mb.on(OrderDelete{.hdr = hdr(), .order_ref = 99});
  EXPECT_EQ(mb.stats().unknown_order, 1u);

  mb.on(add(1, Side::Buy, 600, 999));  // duplicate reference
  EXPECT_EQ(mb.stats().duplicate_order, 1u);
  EXPECT_EQ(*aapl().best(Side::Buy), (Level{.price = 500, .order_count = 1, .qty = 100}));

  mb.on(OrderCancel{.hdr = hdr(), .order_ref = 1, .cancelled_shares = 150});  // more than remains
  EXPECT_EQ(mb.stats().overfill, 1u);
  EXPECT_FALSE(aapl().best(Side::Buy).has_value());  // clamped: the whole order went

  mb.on(add(2, Side::Buy, 500, 10, kAapl));
  mb.on(OrderDelete{.hdr = hdr(kAapl + 1), .order_ref = 2});  // wrong symbol in the message
  EXPECT_EQ(mb.stats().locate_mismatch, 1u);
  EXPECT_FALSE(aapl().best(Side::Buy).has_value());  // removed from its real book anyway

  EXPECT_EQ(mb.stats().book_mismatch, 0u);
}

TEST(MarketBook, FullTableCountsAndDropsTheOrder) {
  MarketBook mb({.max_orders = 2, .levels_per_side = 4});
  mb.on(add(1, Side::Buy, 100, 1));
  mb.on(add(2, Side::Buy, 100, 1));
  mb.on(add(3, Side::Buy, 100, 1));
  EXPECT_EQ(mb.stats().table_full, 1u);
  EXPECT_EQ(mb.book(kAapl).best(Side::Buy)->order_count, 2u);
}

// Every level of every symbol in `mb` must equal the reference book.
void expect_books_equal(const MarketBook& mb, const hft::testing::ReferenceBook& ref, Locate symbols) {
  for (Locate loc = 1; loc <= symbols; ++loc) {
    for (Side side : {Side::Buy, Side::Sell}) {
      const auto want = ref.levels(loc, side);
      const auto& book = mb.book(loc);
      ASSERT_EQ(book.depth(side), want.size()) << "locate " << loc;
      for (std::size_t d = 0; d < want.size(); ++d) {
        ASSERT_EQ(*book.level(side, d), want[d]) << "locate " << loc << " depth " << d;
      }
    }
  }
}

// Differential test: half a million synthetic messages through the fast
// book and the reference book. Checked every 10'000 messages, so a
// divergence is caught near where it happens.
TEST(MarketBook, MatchesReferenceBookOnSyntheticFeed) {
  const SyntheticFeedConfig cfg{.symbols = 6, .messages = 500'000, .target_live_orders = 3'000,
                                .max_level_offset = 24, .seed = 7};
  const auto feed = make_synthetic_feed(cfg);

  MarketBook mb({.max_orders = 8'192, .levels_per_side = 64});
  hft::testing::ReferenceBook ref;

  // Re-frame the feed one message at a time so the books can be compared
  // mid-stream.
  std::span<const std::byte> rest(feed);
  std::uint64_t n = 0;
  while (rest.size() >= 2) {
    const std::size_t len = load_be16(rest.data());
    const auto msg = rest.subspan(2, len);
    ASSERT_EQ(parse_message(msg, mb), ParseStatus::Ok);
    ASSERT_EQ(parse_message(msg, ref), ParseStatus::Ok);
    rest = rest.subspan(2 + len);
    if (++n % 10'000 == 0) {
      ASSERT_NO_FATAL_FAILURE(expect_books_equal(mb, ref, cfg.symbols)) << "after message " << n;
    }
  }
  expect_books_equal(mb, ref, cfg.symbols);
  EXPECT_EQ(mb.live_orders(), ref.live_orders());

  const auto& s = mb.stats();
  EXPECT_EQ(s.unknown_order + s.duplicate_order + s.overfill + s.locate_mismatch + s.table_full + s.book_mismatch, 0u);
  EXPECT_GT(s.executions, 0u);
  EXPECT_GT(s.cancels, 0u);
  EXPECT_GT(s.replaces, 0u);
}

}  // namespace
