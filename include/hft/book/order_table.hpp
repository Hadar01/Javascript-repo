#pragma once

// OrderTable: every live order, keyed by its ITCH order reference number.
//
// An open-addressing hash table with linear probing, allocated once at
// construction and never again. Why not std::unordered_map:
//   - unordered_map allocates a node on every insert and frees it on every
//     erase: a malloc/free pair per order, on the hot path.
//   - Its nodes are scattered over the heap. A lookup reads a bucket array
//     and then follows a pointer, usually two cache misses.
// Here the entries live inline in one flat array. A lookup hashes the key,
// jumps to that slot and scans forward; usually the first slot holds it.
//
// Deletion uses backward shifting rather than tombstones. Tombstones
// ("deleted" markers) pile up over a day of ~100M deletes until every
// lookup scans long runs of them. Backward shifting closes the gap instead,
// so the table stays as good as freshly built.

#include <algorithm>
#include <bit>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

#include "hft/common/types.hpp"

namespace hft::book {

struct OrderEntry {
  OrderRef ref;
  Price price;
  Qty shares;  // remaining
  Locate locate;
  Side side;
};
// 8 + 4 + 4 + 2 + 1 = 19 bytes, padded to 24 for the 8-byte alignment of ref.
static_assert(sizeof(OrderEntry) == 24);

class OrderTable {
 public:
  // Marks an empty slot. Inserting this reference is refused.
  static constexpr OrderRef kEmpty = std::numeric_limits<OrderRef>::max();

  enum class InsertResult : std::uint8_t { Inserted, Duplicate, Full };

  // Holds up to max_orders live orders. The slot count is the next power of
  // two at or above 2 * max_orders, so the table is never more than half
  // full. Linear probing degrades quickly past roughly 70% full.
  explicit OrderTable(std::size_t max_orders)
      : max_orders_(max_orders),
        slots_(std::bit_ceil(std::max<std::size_t>(16, 2 * max_orders)),
               OrderEntry{.ref = kEmpty, .price = 0, .shares = 0, .locate = 0, .side = Side::Buy}),
        mask_(slots_.size() - 1),
        shift_(64 - std::countr_zero(slots_.size())) {}
  // The constructor writes every slot. That touches each page now, so the
  // kernel maps them at startup rather than on first use mid-session (a page
  // fault costs microseconds).

  [[nodiscard]] OrderEntry* find(OrderRef ref) noexcept {
    std::size_t i = home(ref);
    while (true) {
      OrderEntry& s = slots_[i];
      if (s.ref == ref) return &s;
      if (s.ref == kEmpty) return nullptr;
      i = (i + 1) & mask_;
    }
  }

  // Inserting an order that is already present is reported, not applied: the
  // feed is wrong and the old order's state is kept.
  InsertResult insert(const OrderEntry& e) noexcept {
    assert(e.ref != kEmpty);
    std::size_t i = home(e.ref);
    while (true) {
      OrderEntry& s = slots_[i];
      if (s.ref == kEmpty) break;
      if (s.ref == e.ref) [[unlikely]] return InsertResult::Duplicate;
      i = (i + 1) & mask_;
    }
    // Check capacity only after the duplicate check, so a full table still
    // reports duplicates correctly.
    if (size_ == max_orders_) [[unlikely]] return InsertResult::Full;
    slots_[i] = e;
    ++size_;
    return InsertResult::Inserted;
  }

  // Erase the entry `e` points to (from find()). After this, `e` and every
  // other pointer into the table may point at a different order, because
  // later entries can be shifted back into the gap.
  void erase(OrderEntry* e) noexcept {
    std::size_t hole = static_cast<std::size_t>(e - slots_.data());
    std::size_t j = hole;
    while (true) {
      j = (j + 1) & mask_;
      if (slots_[j].ref == kEmpty) break;
      // The entry at j was placed by probing from its home slot up to j. It
      // may move back into the hole only if the hole lies on that path,
      // i.e. its distance home->j is at least the distance hole->j.
      // Otherwise moving it would put it before its home, where find() would
      // never look.
      const std::size_t dist_home = (j - home(slots_[j].ref)) & mask_;
      const std::size_t dist_hole = (j - hole) & mask_;
      if (dist_home >= dist_hole) {
        slots_[hole] = slots_[j];
        hole = j;
      }
    }
    slots_[hole].ref = kEmpty;
    --size_;
  }

  [[nodiscard]] std::size_t size() const noexcept { return size_; }
  [[nodiscard]] std::size_t max_orders() const noexcept { return max_orders_; }
  [[nodiscard]] std::size_t slot_count() const noexcept { return slots_.size(); }

  // The slot a key would occupy in an otherwise empty table. Public for tests.
  [[nodiscard]] std::size_t home(OrderRef ref) const noexcept {
    // Fibonacci hashing: multiply by 2^64 / golden ratio and keep the TOP
    // bits. The low bits of a product depend only on the low bits of the
    // key, but the top bits depend on all of them, so consecutive order
    // references spread evenly across the table. One multiply (~3 cycles)
    // instead of a division by a prime.
    return static_cast<std::size_t>((ref * 0x9E3779B97F4A7C15ULL) >> shift_);
  }

 private:
  std::size_t max_orders_;
  std::size_t size_ = 0;
  std::vector<OrderEntry> slots_;
  std::size_t mask_;  // slot_count - 1; `& mask_` wraps an index for free
  int shift_;         // 64 - log2(slot_count)
};

}  // namespace hft::book
