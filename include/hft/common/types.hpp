#pragma once

#include <cstdint>

namespace hft {

// Plain aliases, not strong types: Price and Qty are both uint32_t, so the
// compiler won't stop you passing one where the other belongs. The tests
// guard against that instead; see LEARNING.md for the trade-off.

// ITCH "Price(4)": fixed point with 4 implied decimal places, so
// $123.45 is 1'234'500. Prices stay integers end to end. Floating point
// can't represent most decimal prices exactly, and == on doubles is a bug.
using Price = std::uint32_t;
using Qty = std::uint32_t;         // shares
using OrderRef = std::uint64_t;    // unique per order for the whole day
using Locate = std::uint16_t;      // per-day symbol index assigned by Nasdaq
using Timestamp = std::uint64_t;   // nanoseconds since midnight (48 bits used)

// The enumerator values are the wire bytes, so decoding is a range check
// plus a cast, with no lookup table.
enum class Side : std::uint8_t { Buy = 'B', Sell = 'S' };

}  // namespace hft
