#pragma once

// ITCH 5.0 message parser.
//
// parse_message() decodes one message and calls handler.on(msg) with the
// decoded struct. parse_binary_file() walks a buffer in Nasdaq's BinaryFILE
// framing ([2-byte big-endian length][message], repeated), which is the
// format of the sample files.
//
// The handler is a template parameter, not an interface with virtual
// functions. The compiler knows the exact handler type, so it can inline
// handler.on() into the parse loop and optimise both together. A virtual
// call is an indirect call per message that blocks all of that.
//
// A handler implements on() only for the messages it cares about. For any
// other type the call (and the decoding) is removed at compile time.
//
// Errors are return values. Nothing here throws or allocates.

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>

#include "hft/itch/messages.hpp"
#include "hft/itch/wire.hpp"

namespace hft::itch {

enum class ParseStatus : std::uint8_t {
  Ok,           // known type, well formed
  UnknownType,  // a type we don't decode ('P', 'Q', 'I', 'H', ...): skipped
  Malformed,    // shorter than its type requires, or a bad field value
};

// True if handler.on(msg) is a valid call.
template <typename H, typename M>
concept Handles = requires(H& handler, const M& msg) { handler.on(msg); };

namespace detail {

[[nodiscard]] inline Header decode_header(const std::byte* p) noexcept {
  return Header{
      .locate = load_be16(p + 1),
      .tracking = load_be16(p + 3),
      .timestamp = load_be48(p + 5),
  };
}

}  // namespace detail

// Decode one message (without its length prefix) and pass it to the handler.
//
// always_inline: `inline` and templates only *allow* inlining, and GCC
// declined for a function this size, which was measured (see LEARNING.md,
// stage 1). Not inlined, every message costs a real call, and the handler's
// state lives in memory instead of registers.
template <typename Handler>
[[gnu::always_inline]] inline ParseStatus parse_message(std::span<const std::byte> msg, Handler& handler) {
  using detail::decode_header;
  if (msg.empty()) [[unlikely]] {
    return ParseStatus::Malformed;
  }
  const std::byte* p = msg.data();
  const std::size_t n = msg.size();

  // A switch on a dense set of chars compiles to a jump table: one indirect
  // jump, whose target the CPU's branch predictor learns from recent
  // message types. Every length check below is almost never true, so
  // [[unlikely]] keeps the error paths out of the hot code.
  switch (static_cast<char>(p[0])) {
    case SystemEvent::kType: {
      if (n < SystemEvent::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, SystemEvent>) {
        handler.on(SystemEvent{
            .hdr = decode_header(p),
            .event_code = static_cast<char>(p[11]),
        });
      }
      return ParseStatus::Ok;
    }

    case StockDirectory::kType: {
      if (n < StockDirectory::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, StockDirectory>) {
        StockDirectory m{.hdr = decode_header(p), .stock = {}};
        std::memcpy(m.stock.data(), p + 11, m.stock.size());
        handler.on(m);
      }
      return ParseStatus::Ok;
    }

    case AddOrder::kType:
    case AddOrder::kTypeMpid: {
      const std::size_t need = static_cast<char>(p[0]) == AddOrder::kType
                                   ? AddOrder::kWireSize
                                   : AddOrder::kWireSizeMpid;
      if (n < need) [[unlikely]] return ParseStatus::Malformed;
      // Check the side before casting: a Side holding any other byte would be
      // a value the rest of the code assumes can't exist.
      const char side = static_cast<char>(p[19]);
      if (side != 'B' && side != 'S') [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, AddOrder>) {
        handler.on(AddOrder{
            .hdr = decode_header(p),
            .order_ref = load_be64(p + 11),
            .side = static_cast<Side>(side),
            .shares = load_be32(p + 20),
            .price = load_be32(p + 32),
        });
      }
      return ParseStatus::Ok;
    }

    case OrderExecuted::kType: {
      if (n < OrderExecuted::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, OrderExecuted>) {
        handler.on(OrderExecuted{
            .hdr = decode_header(p),
            .order_ref = load_be64(p + 11),
            .executed_shares = load_be32(p + 19),
            .match_number = load_be64(p + 23),
        });
      }
      return ParseStatus::Ok;
    }

    case OrderExecutedWithPrice::kType: {
      if (n < OrderExecutedWithPrice::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, OrderExecutedWithPrice>) {
        handler.on(OrderExecutedWithPrice{
            .hdr = decode_header(p),
            .order_ref = load_be64(p + 11),
            .executed_shares = load_be32(p + 19),
            .match_number = load_be64(p + 23),
            .printable = static_cast<char>(p[31]),
            .execution_price = load_be32(p + 32),
        });
      }
      return ParseStatus::Ok;
    }

    case OrderCancel::kType: {
      if (n < OrderCancel::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, OrderCancel>) {
        handler.on(OrderCancel{
            .hdr = decode_header(p),
            .order_ref = load_be64(p + 11),
            .cancelled_shares = load_be32(p + 19),
        });
      }
      return ParseStatus::Ok;
    }

    case OrderDelete::kType: {
      if (n < OrderDelete::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, OrderDelete>) {
        handler.on(OrderDelete{
            .hdr = decode_header(p),
            .order_ref = load_be64(p + 11),
        });
      }
      return ParseStatus::Ok;
    }

    case OrderReplace::kType: {
      if (n < OrderReplace::kWireSize) [[unlikely]] return ParseStatus::Malformed;
      if constexpr (Handles<Handler, OrderReplace>) {
        handler.on(OrderReplace{
            .hdr = decode_header(p),
            .original_ref = load_be64(p + 11),
            .new_ref = load_be64(p + 19),
            .shares = load_be32(p + 27),
            .price = load_be32(p + 31),
        });
      }
      return ParseStatus::Ok;
    }

    default:
      return ParseStatus::UnknownType;
  }
}

struct FeedStats {
  std::uint64_t messages = 0;      // length-prefixed messages found
  std::uint64_t unknown_type = 0;  // skipped: types we don't decode
  std::uint64_t malformed = 0;
  std::size_t bytes_consumed = 0;  // up to the end of the last whole message
  std::size_t trailing_bytes = 0;  // an incomplete message at the end of the buffer
};

// Walk a buffer in BinaryFILE framing and parse every complete message.
// A message cut off by the end of the buffer is not parsed; its bytes are
// reported in trailing_bytes. That happens with a file cut by HEAD_MB.
template <typename Handler>
FeedStats parse_binary_file(std::span<const std::byte> buf, Handler& handler) {
  FeedStats stats;
  const std::byte* const data = buf.data();
  const std::size_t size = buf.size();
  std::size_t off = 0;

  // Written as "remaining >= needed" rather than "off + needed <= size", so
  // the comparison can't overflow.
  while (size - off >= 2) {
    const std::size_t len = load_be16(data + off);
    if (size - off - 2 < len) {
      break;  // the length prefix promises more bytes than are left
    }
    ++stats.messages;
    switch (parse_message(std::span<const std::byte>(data + off + 2, len), handler)) {
      case ParseStatus::Ok:
        break;
      case ParseStatus::UnknownType:
        ++stats.unknown_type;
        break;
      case ParseStatus::Malformed:
        ++stats.malformed;
        break;
    }
    off += 2 + len;
  }
  stats.bytes_consumed = off;
  stats.trailing_bytes = size - off;
  return stats;
}

}  // namespace hft::itch
