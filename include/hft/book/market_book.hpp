#pragma once

// MarketBook: rebuilds the order book of every symbol from ITCH messages.
//
// It is an ITCH handler: pass it straight to itch::parse_binary_file().
//   - Order state (price, remaining shares, side) lives in one OrderTable
//     for the whole market, because order references are unique across all
//     symbols.
//   - Price levels live in one OrderBook per symbol, in a vector indexed by
//     stock locate. Lookup is an array index, not a hash map.
//
// Bad input never crashes it or corrupts it silently. An impossible message
// (unknown order, duplicate reference, executing more shares than remain) is
// counted in stats() and handled conservatively.
//
// The handlers are defined in the class body, which makes them implicitly
// inline, so the compiler can inline them into the parse loop.

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string_view>
#include <vector>

#include "hft/book/order_book.hpp"
#include "hft/book/order_table.hpp"
#include "hft/common/types.hpp"
#include "hft/itch/messages.hpp"

namespace hft::book {

struct MarketBookConfig {
  std::size_t max_orders = std::size_t{1} << 20;  // peak live orders, all symbols
  std::size_t levels_per_side = 64;               // reserved per symbol
};

struct BookStats {
  // Message counts, including messages that turned out to be anomalies.
  std::uint64_t adds = 0;
  std::uint64_t executions = 0;
  std::uint64_t cancels = 0;
  std::uint64_t deletes = 0;
  std::uint64_t replaces = 0;
  std::uint64_t peak_orders = 0;
  // Anomalies. All zero on a clean feed read from its first message.
  std::uint64_t unknown_order = 0;    // E/C/X/D/U for a reference we don't have
  std::uint64_t duplicate_order = 0;  // A/F/U adding a reference that already exists
  std::uint64_t overfill = 0;         // more shares executed/cancelled than remained
  std::uint64_t locate_mismatch = 0;  // message's stock differs from the order's
  std::uint64_t table_full = 0;       // order dropped: raise max_orders
  std::uint64_t book_mismatch = 0;    // level missing for a live order: a bug
};

class MarketBook {
 public:
  static constexpr std::size_t kMaxLocates = std::size_t{1} << 16;  // Locate is 16-bit
  static constexpr std::array<char, 8> kNoSymbol = {' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '};

  explicit MarketBook(const MarketBookConfig& cfg = {})
      : levels_per_side_(cfg.levels_per_side),
        orders_(cfg.max_orders),
        books_(kMaxLocates),
        symbols_(kMaxLocates, kNoSymbol) {}

  // Pre-market: record the ticker and reserve the symbol's levels, so the
  // allocation happens now and not on its first order.
  void on(const itch::StockDirectory& m) {
    symbols_[m.hdr.locate] = m.stock;
    books_[m.hdr.locate].reserve(levels_per_side_);
  }

  void on(const itch::AddOrder& m) { add(m.hdr.locate, m.order_ref, m.side, m.price, m.shares); }

  void on(const itch::OrderExecuted& m) noexcept {
    ++stats_.executions;
    reduce(m.hdr.locate, m.order_ref, m.executed_shares, /*delete_all=*/false);
  }

  void on(const itch::OrderExecutedWithPrice& m) noexcept {
    ++stats_.executions;
    reduce(m.hdr.locate, m.order_ref, m.executed_shares, /*delete_all=*/false);
  }

  void on(const itch::OrderCancel& m) noexcept {
    ++stats_.cancels;
    reduce(m.hdr.locate, m.order_ref, m.cancelled_shares, /*delete_all=*/false);
  }

  void on(const itch::OrderDelete& m) noexcept {
    ++stats_.deletes;
    reduce(m.hdr.locate, m.order_ref, 0, /*delete_all=*/true);
  }

  void on(const itch::OrderReplace& m) {
    ++stats_.replaces;
    OrderEntry* old = orders_.find(m.original_ref);
    if (old == nullptr) [[unlikely]] {
      ++stats_.unknown_order;
      return;
    }
    // Copy what we need before erase(): erasing shifts table entries, so
    // `old` may point at a different order afterwards.
    const Side side = old->side;
    const Locate locate = old->locate;
    remove(old, old->shares, /*order_gone=*/true);
    add(locate, m.new_ref, side, m.price, m.shares);
  }

  [[nodiscard]] const OrderBook& book(Locate locate) const noexcept { return books_[locate]; }

  [[nodiscard]] std::string_view symbol(Locate locate) const noexcept {
    return itch::trim_symbol(symbols_[locate]);
  }

  // Linear search over all locates: for setup, not for the hot path.
  [[nodiscard]] std::optional<Locate> find_locate(std::string_view ticker) const noexcept {
    for (std::size_t i = 0; i < kMaxLocates; ++i) {
      if (itch::trim_symbol(symbols_[i]) == ticker) return static_cast<Locate>(i);
    }
    return std::nullopt;
  }

  [[nodiscard]] const BookStats& stats() const noexcept { return stats_; }
  [[nodiscard]] std::size_t live_orders() const noexcept { return orders_.size(); }

  // Allocations made after setup because a symbol needed more levels than
  // levels_per_side. Zero means the hot path never allocated.
  [[nodiscard]] std::uint64_t level_growth_events() const noexcept {
    std::uint64_t n = 0;
    for (const auto& b : books_) n += b.growth_events();
    return n;
  }

 private:
  void add(Locate locate, OrderRef ref, Side side, Price price, Qty shares) {
    ++stats_.adds;
    const auto r = orders_.insert(
        OrderEntry{.ref = ref, .price = price, .shares = shares, .locate = locate, .side = side});
    if (r != OrderTable::InsertResult::Inserted) [[unlikely]] {
      if (r == OrderTable::InsertResult::Duplicate) {
        ++stats_.duplicate_order;
      } else {
        ++stats_.table_full;
      }
      return;
    }
    if (orders_.size() > stats_.peak_orders) stats_.peak_orders = orders_.size();
    books_[locate].add(side, price, shares);
  }

  // Take shares off an order (delete_all: all of them).
  void reduce(Locate locate, OrderRef ref, Qty shares, bool delete_all) noexcept {
    OrderEntry* o = orders_.find(ref);
    if (o == nullptr) [[unlikely]] {
      ++stats_.unknown_order;
      return;
    }
    if (o->locate != locate) [[unlikely]] ++stats_.locate_mismatch;  // trust the order's own locate
    if (delete_all) {
      shares = o->shares;
    } else if (shares > o->shares) [[unlikely]] {
      ++stats_.overfill;
      shares = o->shares;
    }
    remove(o, shares, /*order_gone=*/shares == o->shares);
  }

  void remove(OrderEntry* o, Qty shares, bool order_gone) noexcept {
    if (!books_[o->locate].reduce(o->side, o->price, shares, order_gone)) [[unlikely]] {
      ++stats_.book_mismatch;
    }
    if (order_gone) {
      orders_.erase(o);  // invalidates o
    } else {
      o->shares -= shares;
    }
  }

  std::size_t levels_per_side_;
  OrderTable orders_;
  std::vector<OrderBook> books_;                 // indexed by locate
  std::vector<std::array<char, 8>> symbols_;     // indexed by locate
  BookStats stats_;
};

}  // namespace hft::book
