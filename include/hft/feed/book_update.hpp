#pragma once

// BookUpdate: what the feed thread sends to the strategy thread.
//
// A self-contained snapshot of the top kDepth levels of one symbol's book,
// sent whenever those levels change. Why a snapshot rather than the raw
// message or a delta:
//   - The strategy thread doesn't need a book of its own. All the order
//     bookkeeping stays on the feed thread.
//   - Snapshots are idempotent. If one is dropped because the ring is full,
//     the next one carries the full state again. A dropped delta would
//     corrupt the receiver's book until a resync.
//
// Exactly 128 bytes, aligned to 64: two whole cache lines, never straddling
// a third, and no two updates share a line in the ring.

#include <array>
#include <cstddef>
#include <cstdint>
#include <type_traits>

#include "hft/common/types.hpp"

namespace hft::feed {

struct alignas(64) BookUpdate {
  static constexpr std::size_t kDepth = 5;

  struct Level {
    Price price;
    std::uint32_t qty;  // shares at this level, saturated at UINT32_MAX
    bool operator==(const Level&) const = default;
  };

  std::uint64_t seq;          // increases by 1 per update the feed tried to send; a gap means a drop
  Timestamp exch_ts;          // ITCH timestamp of the message that changed the book
  std::uint64_t publish_tsc;  // rdtsc() just before the push, for hop latency
  Locate locate;
  std::uint8_t bid_depth;     // valid entries in bids (<= kDepth)
  std::uint8_t ask_depth;
  std::array<Level, kDepth> bids;  // best first; unused entries are zero
  std::array<Level, kDepth> asks;  // best first; unused entries are zero
};

static_assert(std::is_trivially_copyable_v<BookUpdate>);
// 8+8+8+2+1+1 = 28 bytes of header, then 2*5*8 = 80 bytes of levels (4-byte
// aligned, so no padding between), = 108, rounded up to 128 by alignas(64).
static_assert(sizeof(BookUpdate) == 128);

// Same book content (ignores seq and the timestamps)?
[[nodiscard]] inline bool same_levels(const BookUpdate& a, const BookUpdate& b) noexcept {
  return a.locate == b.locate && a.bid_depth == b.bid_depth && a.ask_depth == b.ask_depth &&
         a.bids == b.bids && a.asks == b.asks;
}

}  // namespace hft::feed
