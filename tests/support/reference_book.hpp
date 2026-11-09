#pragma once

// ReferenceBook: the obviously-correct, slow version of MarketBook.
//
// It uses the standard containers in the most direct way: unordered_map for
// orders, std::map for price levels. It assumes valid input. Tests feed both
// books the same messages and require identical results: differential
// testing. If the fast book disagrees, the fast book is wrong.
//
// It is also the "naive" baseline in the benchmarks.

#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <unordered_map>
#include <vector>

#include "hft/book/order_book.hpp"
#include "hft/common/types.hpp"
#include "hft/itch/messages.hpp"

namespace hft::testing {

class ReferenceBook {
 public:
  void on(const itch::AddOrder& m) { add(m.hdr.locate, m.order_ref, m.side, m.price, m.shares); }
  void on(const itch::OrderExecuted& m) { reduce(m.order_ref, m.executed_shares); }
  void on(const itch::OrderExecutedWithPrice& m) { reduce(m.order_ref, m.executed_shares); }
  void on(const itch::OrderCancel& m) { reduce(m.order_ref, m.cancelled_shares); }
  void on(const itch::OrderDelete& m) { reduce(m.order_ref, orders_.at(m.order_ref).shares); }
  void on(const itch::OrderReplace& m) {
    const Order o = orders_.at(m.original_ref);
    reduce(m.original_ref, o.shares);
    add(o.locate, m.new_ref, o.side, m.price, m.shares);
  }

  // Levels of one side, best first.
  [[nodiscard]] std::vector<book::Level> levels(Locate locate, Side side) const {
    std::vector<book::Level> out;
    auto copy = [&](const auto& side_map) {
      for (const auto& [price, lvl] : side_map) {
        out.push_back(book::Level{.price = price, .order_count = lvl.count, .qty = lvl.qty});
      }
    };
    if (side == Side::Buy) {
      if (auto it = bids_.find(locate); it != bids_.end()) copy(it->second);
    } else {
      if (auto it = asks_.find(locate); it != asks_.end()) copy(it->second);
    }
    return out;
  }

  [[nodiscard]] std::size_t live_orders() const { return orders_.size(); }

 private:
  struct Order {
    Locate locate;
    Side side;
    Price price;
    Qty shares;
  };
  struct Agg {
    std::uint64_t qty = 0;
    std::uint32_t count = 0;
  };
  // std::greater puts the highest bid first; asks use the default (lowest first).
  using BidMap = std::map<Price, Agg, std::greater<>>;
  using AskMap = std::map<Price, Agg>;

  void add(Locate locate, OrderRef ref, Side side, Price price, Qty shares) {
    const bool inserted = orders_.emplace(ref, Order{locate, side, price, shares}).second;
    assert(inserted);
    (void)inserted;
    Agg& a = side == Side::Buy ? bids_[locate][price] : asks_[locate][price];
    a.qty += shares;
    ++a.count;
  }

  void reduce(OrderRef ref, Qty shares) {
    auto it = orders_.find(ref);
    assert(it != orders_.end());
    Order& o = it->second;
    assert(shares <= o.shares);
    o.shares -= shares;
    const bool gone = o.shares == 0;
    if (o.side == Side::Buy) {
      apply(bids_[o.locate], o.price, shares, gone);
    } else {
      apply(asks_[o.locate], o.price, shares, gone);
    }
    if (gone) orders_.erase(it);
  }

  template <typename Map>
  static void apply(Map& m, Price price, Qty shares, bool gone) {
    auto it = m.find(price);
    assert(it != m.end());
    it->second.qty -= shares;
    if (gone && --it->second.count == 0) m.erase(it);
  }

  std::unordered_map<OrderRef, Order> orders_;
  std::unordered_map<Locate, BidMap> bids_;
  std::unordered_map<Locate, AskMap> asks_;
};

}  // namespace hft::testing
