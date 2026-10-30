#pragma once

// OrderBook: the price levels of one symbol, both sides.
//
// Each level aggregates the orders resting at one price: total shares and
// order count. The individual orders live in OrderTable; this class only
// sees "add q shares at price p" and "remove q shares at price p".
//
// Each side is a std::vector<Level> sorted with the BEST price at the BACK:
//   bids ascending  (highest bid last)
//   asks descending (lowest ask last)
// Why:
//   - Almost all activity happens within a few levels of the best price.
//     With the best price at the back, those updates touch the end of the
//     vector, and inserting or erasing there shifts only a few elements.
//   - Levels are contiguous, 16 bytes each, 4 per cache line. Scanning the
//     top 10 levels touches 3 cache lines. The hardware prefetcher handles
//     the sequential access.
//   - The search is a linear scan from the back. It ends after a few steps
//     for near-the-top prices, and its branch is easy to predict. A binary
//     search would jump around the vector, and its comparison outcomes are
//     close to random, so it mispredicts.
// The alternative, std::map<Price, Level>, allocates a node per new level,
// and each step down the tree is a dependent pointer load that can miss the
// cache.

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

#include "hft/common/types.hpp"

namespace hft::book {

struct Level {
  Price price;
  std::uint32_t order_count;
  std::uint64_t qty;  // 64-bit: the sum of many 32-bit order sizes
  bool operator==(const Level&) const = default;
};
static_assert(sizeof(Level) == 16);

class OrderBook {
 public:
  OrderBook() = default;

  // Allocate room for n levels per side up front. Done when the symbol is
  // announced (stock directory message), before trading starts.
  void reserve(std::size_t levels_per_side) {
    bids_.reserve(levels_per_side);
    asks_.reserve(levels_per_side);
  }

  // A new order of qty shares at price.
  void add(Side side, Price price, Qty qty) {
    if (side == Side::Buy) {
      add_impl<Side::Buy>(bids_, price, qty);
    } else {
      add_impl<Side::Sell>(asks_, price, qty);
    }
  }

  // Remove qty shares from the level at price. order_gone says whether the
  // order itself left the book (fully executed, cancelled or deleted), so
  // the level's order count drops by one. Returns false if no level exists
  // at that price: the caller's order state disagrees with the book.
  bool reduce(Side side, Price price, Qty qty, bool order_gone) noexcept {
    return side == Side::Buy ? reduce_impl<Side::Buy>(bids_, price, qty, order_gone)
                             : reduce_impl<Side::Sell>(asks_, price, qty, order_gone);
  }

  // Level `depth` levels from the top of the side (0 = best), if it exists.
  // Returned by value: a pointer into the vector would silently point at the
  // wrong level after the next insert or erase shifts the elements.
  [[nodiscard]] std::optional<Level> level(Side side, std::size_t depth) const noexcept {
    const auto& v = levels(side);
    if (depth >= v.size()) return std::nullopt;
    return v[v.size() - 1 - depth];
  }

  [[nodiscard]] std::optional<Level> best(Side side) const noexcept { return level(side, 0); }
  [[nodiscard]] std::size_t depth(Side side) const noexcept { return levels(side).size(); }

  // How many times an add had to grow a side's vector (i.e. allocate)
  // because more levels existed than were reserved.
  [[nodiscard]] std::uint64_t growth_events() const noexcept { return growth_events_; }

 private:
  [[nodiscard]] const std::vector<Level>& levels(Side side) const noexcept {
    return side == Side::Buy ? bids_ : asks_;
  }

  // Is price a worse than price b on side S? Bids: lower is worse. Asks:
  // higher is worse. `if constexpr` picks one comparison at compile time, so
  // the scan loop below has no side branch in it.
  template <Side S>
  static constexpr bool worse(Price a, Price b) noexcept {
    if constexpr (S == Side::Buy) {
      return a < b;
    } else {
      return a > b;
    }
  }

  // Scan from the best (back) toward the worst (front). Returns i such that
  // every level at index >= i is strictly better than `price`. So either
  // v[i - 1] is the level at `price`, or `price` belongs at position i.
  template <Side S>
  static std::size_t find_from_top(const std::vector<Level>& v, Price price) noexcept {
    std::size_t i = v.size();
    while (i > 0 && worse<S>(price, v[i - 1].price)) --i;
    return i;
  }

  template <Side S>
  void add_impl(std::vector<Level>& v, Price price, Qty qty) {
    const std::size_t i = find_from_top<S>(v, price);
    if (i > 0 && v[i - 1].price == price) {
      v[i - 1].qty += qty;
      ++v[i - 1].order_count;
      return;
    }
    if (v.size() == v.capacity()) [[unlikely]] ++growth_events_;
    // The cast avoids a -Wsign-conversion warning: iterator arithmetic uses
    // the signed std::ptrdiff_t, and i is an unsigned size_t.
    v.insert(v.begin() + static_cast<std::ptrdiff_t>(i), Level{.price = price, .order_count = 1, .qty = qty});
  }

  template <Side S>
  bool reduce_impl(std::vector<Level>& v, Price price, Qty qty, bool order_gone) noexcept {
    const std::size_t i = find_from_top<S>(v, price);
    if (i == 0 || v[i - 1].price != price) [[unlikely]] return false;
    Level& lvl = v[i - 1];
    assert(lvl.qty >= qty);
    lvl.qty -= qty;
    if (order_gone) {
      assert(lvl.order_count > 0);
      if (--lvl.order_count == 0) {
        assert(lvl.qty == 0);
        v.erase(v.begin() + static_cast<std::ptrdiff_t>(i - 1));
      }
    }
    return true;
  }

  std::vector<Level> bids_;  // ascending: best (highest) at the back
  std::vector<Level> asks_;  // descending: best (lowest) at the back
  std::uint64_t growth_events_ = 0;
};

}  // namespace hft::book
