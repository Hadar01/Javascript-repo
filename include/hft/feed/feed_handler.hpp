#pragma once

// FeedHandler: the feed thread's ITCH handler.
//
// It forwards every message to the MarketBook, and after each message that
// touched a subscribed symbol it builds a top-of-book snapshot
// (BookUpdate) and pushes it into the ring for the strategy thread.
//
//   - Subscriptions are set up before the feed starts, by ticker or by
//     stock locate. The per-message check is one bit in an 8 KB bitset,
//     which stays in L1 cache. Most messages are for other symbols and stop
//     there.
//   - Nothing is sent if the top kDepth levels didn't change (an order
//     added deeper in the book, for example).
//   - When the ring is full: Drop (default) counts and drops the update, so
//     a slow strategy can never stall the feed. Wait spins until there is
//     room, which loses nothing but makes the feed as slow as the strategy.
//   - Every update the feed tries to send gets the next sequence number, so
//     the strategy detects drops as gaps.

#include <bitset>
#include <cstdint>
#include <limits>
#include <string>
#include <string_view>
#include <vector>

#include "hft/book/market_book.hpp"
#include "hft/common/cpu.hpp"
#include "hft/concurrency/spsc_ring.hpp"
#include "hft/feed/book_update.hpp"
#include "hft/itch/messages.hpp"
#include "hft/itch/parser.hpp"

namespace hft::feed {

// 4096 updates * 128 bytes = 512 KB: absorbs bursts while still fitting in L2.
using UpdateRing = SpscRing<BookUpdate, 4096>;

enum class OnFull : std::uint8_t { Drop, Wait };

struct FeedHandlerConfig {
  book::MarketBookConfig book{};
  OnFull on_full = OnFull::Drop;
};

struct PublishStats {
  std::uint64_t published = 0;  // pushed into the ring
  std::uint64_t unchanged = 0;  // subscribed symbol touched, top levels the same: nothing sent
  std::uint64_t dropped = 0;    // ring full (Drop policy)
};

class FeedHandler {
 public:
  FeedHandler(const FeedHandlerConfig& cfg, UpdateRing& out)
      : book_(cfg.book), out_(out), on_full_(cfg.on_full), slot_of_(book::MarketBook::kMaxLocates, kNoSlot) {}

  // --- setup, before the feed starts -------------------------------------
  // By ticker: takes effect when the symbol's stock directory message arrives.
  void subscribe_ticker(std::string_view ticker) { tickers_.emplace_back(ticker); }

  void subscribe_locate(Locate locate) {
    if (slot_of_[locate] != kNoSlot) return;
    slot_of_[locate] = static_cast<std::uint16_t>(last_sent_.size());
    // Start from "empty book on both sides". The first change is sent; an
    // update that leaves the book empty is not.
    BookUpdate empty{};
    empty.locate = locate;
    last_sent_.push_back(empty);
    subscribed_.set(locate);
  }

  // --- ITCH handler ---------------------------------------------------------
  void on(const itch::StockDirectory& m) {
    book_.on(m);
    for (const auto& t : tickers_) {
      if (itch::trim_symbol(m.stock) == t) subscribe_locate(m.hdr.locate);
    }
  }

  template <typename M>
    requires itch::Handles<book::MarketBook, M>
  void on(const M& m) {
    book_.on(m);
    if (subscribed_.test(m.hdr.locate)) publish(m.hdr.locate, m.hdr.timestamp);
  }

  [[nodiscard]] const book::MarketBook& book() const noexcept { return book_; }
  [[nodiscard]] const PublishStats& stats() const noexcept { return stats_; }

  // The top of the book as the strategy would see it. Public for tests.
  [[nodiscard]] BookUpdate snapshot(Locate locate) const noexcept {
    BookUpdate u{};
    u.locate = locate;
    const book::OrderBook& b = book_.book(locate);
    u.bid_depth = fill(b, Side::Buy, u.bids);
    u.ask_depth = fill(b, Side::Sell, u.asks);
    return u;
  }

 private:
  static constexpr std::uint16_t kNoSlot = 0xFFFF;

  static std::uint8_t fill(const book::OrderBook& b, Side side,
                           std::array<BookUpdate::Level, BookUpdate::kDepth>& out) noexcept {
    std::uint8_t n = 0;
    for (std::size_t d = 0; d < BookUpdate::kDepth; ++d) {
      const auto lvl = b.level(side, d);
      if (!lvl) break;
      // Saturate rather than wrap: a level bigger than 4.29 billion shares
      // shows as the maximum, never as a small number.
      constexpr std::uint64_t kMax = std::numeric_limits<std::uint32_t>::max();
      const std::uint64_t q = lvl->qty < kMax ? lvl->qty : kMax;
      out[d] = BookUpdate::Level{.price = lvl->price, .qty = static_cast<std::uint32_t>(q)};
      ++n;
    }
    return n;
  }

  void publish(Locate locate, Timestamp exch_ts) noexcept {
    BookUpdate u = snapshot(locate);
    BookUpdate& last = last_sent_[slot_of_[locate]];
    if (same_levels(u, last)) {
      ++stats_.unchanged;
      return;
    }
    u.seq = next_seq_++;
    u.exch_ts = exch_ts;
    u.publish_tsc = rdtsc();
    if (on_full_ == OnFull::Wait) {
      while (!out_.try_push(u)) cpu_relax();
    } else if (!out_.try_push(u)) {
      // Keep `last` as the last update the strategy actually received, so
      // the next change is compared against what it really has.
      ++stats_.dropped;
      return;
    }
    ++stats_.published;
    last = u;
  }

  book::MarketBook book_;
  UpdateRing& out_;
  OnFull on_full_;
  std::bitset<book::MarketBook::kMaxLocates> subscribed_;  // 8 KB: the per-message check
  std::vector<std::uint16_t> slot_of_;                     // locate -> index into last_sent_
  std::vector<BookUpdate> last_sent_;                      // one per subscribed symbol
  std::vector<std::string> tickers_;                       // setup only
  std::uint64_t next_seq_ = 0;
  PublishStats stats_;
};

}  // namespace hft::feed
