#pragma once

// Decoded ITCH 5.0 messages: the ones the order book needs, plus the two
// that give context (system events and the stock directory).
//
// These are host-order, naturally aligned structs, not overlays of the wire
// bytes. The parser fills them field by field from the buffer (see
// parser.hpp). Once the parser and the handler are inlined together, the
// compiler drops the decoding of any field the handler never reads, so a
// decoded struct costs no more than reading the bytes directly.
//
// Only fields we use are decoded. The comment on each struct gives the
// type byte and wire size, and each field's comment gives its byte offset
// in the message.

#include <array>
#include <cstddef>
#include <string_view>

#include "hft/common/types.hpp"

namespace hft::itch {

// Every message starts with these 11 bytes:
// type(1) stock_locate(2) tracking_number(2) timestamp(6)
struct Header {
  Locate locate;           // @1. 0 for messages not about one stock
  std::uint16_t tracking;  // @3. Nasdaq internal tracking number
  Timestamp timestamp;     // @5. ns since midnight, 48-bit
  bool operator==(const Header&) const = default;
};
inline constexpr std::size_t kHeaderSize = 11;

// 'S', 12 bytes
struct SystemEvent {
  static constexpr char kType = 'S';
  static constexpr std::size_t kWireSize = 12;
  Header hdr;
  char event_code;  // @11. 'O' start of messages, 'S' start of system hours,
                    //      'Q' market open, 'M' market close, 'E', 'C' ...
  bool operator==(const SystemEvent&) const = default;
};

// 'R', 39 bytes. Sent once per symbol before trading starts; maps
// stock_locate to the ticker.
struct StockDirectory {
  static constexpr char kType = 'R';
  static constexpr std::size_t kWireSize = 39;
  Header hdr;
  std::array<char, 8> stock;  // @11. ticker, padded on the right with spaces
  bool operator==(const StockDirectory&) const = default;
};

// 'A' (36 bytes) or 'F' (40 bytes, adds a 4-byte MPID at @36, which we
// don't use). A new displayed limit order.
struct AddOrder {
  static constexpr char kType = 'A';
  static constexpr std::size_t kWireSize = 36;
  static constexpr char kTypeMpid = 'F';
  static constexpr std::size_t kWireSizeMpid = 40;
  Header hdr;
  OrderRef order_ref;  // @11
  Side side;           // @19 'B' or 'S'
  Qty shares;          // @20
                       // @24 stock(8): skipped, hdr.locate says the same
  Price price;         // @32
  bool operator==(const AddOrder&) const = default;
};

// 'E', 31 bytes. A resting order traded (partly or fully) at its own price.
struct OrderExecuted {
  static constexpr char kType = 'E';
  static constexpr std::size_t kWireSize = 31;
  Header hdr;
  OrderRef order_ref;           // @11
  Qty executed_shares;          // @19
  std::uint64_t match_number;   // @23
  bool operator==(const OrderExecuted&) const = default;
};

// 'C', 36 bytes. Like 'E', but traded at a different price than the order's
// own price (e.g. in an auction). The book still reduces the order at its
// resting price.
struct OrderExecutedWithPrice {
  static constexpr char kType = 'C';
  static constexpr std::size_t kWireSize = 36;
  Header hdr;
  OrderRef order_ref;           // @11
  Qty executed_shares;          // @19
  std::uint64_t match_number;   // @23
  char printable;               // @31 'Y' / 'N': counts toward volume?
  Price execution_price;        // @32
  bool operator==(const OrderExecutedWithPrice&) const = default;
};

// 'X', 23 bytes. Part of an order cancelled; the rest stays on the book.
struct OrderCancel {
  static constexpr char kType = 'X';
  static constexpr std::size_t kWireSize = 23;
  Header hdr;
  OrderRef order_ref;      // @11
  Qty cancelled_shares;    // @19
  bool operator==(const OrderCancel&) const = default;
};

// 'D', 19 bytes. Whole order removed.
struct OrderDelete {
  static constexpr char kType = 'D';
  static constexpr std::size_t kWireSize = 19;
  Header hdr;
  OrderRef order_ref;  // @11
  bool operator==(const OrderDelete&) const = default;
};

// 'U', 35 bytes. Cancel-replace: the original order is removed and a new one
// takes its place under a new reference number. Side and stock carry over
// from the original. The new order loses time priority.
struct OrderReplace {
  static constexpr char kType = 'U';
  static constexpr std::size_t kWireSize = 35;
  Header hdr;
  OrderRef original_ref;  // @11
  OrderRef new_ref;       // @19
  Qty shares;             // @27
  Price price;            // @31
  bool operator==(const OrderReplace&) const = default;
};

// "AAPL    " -> "AAPL"
[[nodiscard]] inline std::string_view trim_symbol(const std::array<char, 8>& s) noexcept {
  std::string_view v(s.data(), s.size());
  const auto end = v.find_last_not_of(' ');
  return end == std::string_view::npos ? std::string_view{} : v.substr(0, end + 1);
}

}  // namespace hft::itch
