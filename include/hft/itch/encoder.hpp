#pragma once

// ITCH 5.0 encoder: the inverse of parser.hpp. It is used to build test
// inputs and synthetic feeds, never on the hot path, so it appends to a
// std::vector and lets it allocate.
//
// encode(msg, out) appends the bare message. encode_framed(msg, out) appends
// it with its BinaryFILE length prefix. Fields we don't decode are written
// as spaces (text fields) or zeros (numbers).

#include <array>
#include <cstddef>
#include <cstring>
#include <vector>

#include "hft/itch/messages.hpp"
#include "hft/itch/wire.hpp"

namespace hft::itch {

namespace detail {

// Grow `out` by n zero bytes and return a pointer to the first new byte.
inline std::byte* grow(std::vector<std::byte>& out, std::size_t n) {
  const std::size_t old = out.size();
  out.resize(old + n);
  return out.data() + old;
}

inline std::byte* put_header(std::byte* p, char type, const Header& h) noexcept {
  p[0] = static_cast<std::byte>(type);
  store_be16(p + 1, h.locate);
  store_be16(p + 3, h.tracking);
  store_be48(p + 5, h.timestamp);
  return p;
}

inline void put_chars(std::byte* p, const char* s, std::size_t n) noexcept {
  std::memcpy(p, s, n);
}

}  // namespace detail

inline void encode(const SystemEvent& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, SystemEvent::kWireSize), SystemEvent::kType, m.hdr);
  p[11] = static_cast<std::byte>(m.event_code);
}

inline void encode(const StockDirectory& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, StockDirectory::kWireSize), StockDirectory::kType, m.hdr);
  detail::put_chars(p + 11, m.stock.data(), m.stock.size());
  // The remaining 20 bytes (market category, round lot size, ...) are not
  // decoded; spaces keep the text fields well formed.
  std::memset(p + 19, ' ', StockDirectory::kWireSize - 19);
}

inline void encode(const AddOrder& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, AddOrder::kWireSize), AddOrder::kType, m.hdr);
  store_be64(p + 11, m.order_ref);
  p[19] = static_cast<std::byte>(m.side);
  store_be32(p + 20, m.shares);
  std::memset(p + 24, ' ', 8);  // stock symbol, not decoded
  store_be32(p + 32, m.price);
}

// 'F': the same order, plus the 4-byte market participant ID at @36.
inline void encode_with_mpid(const AddOrder& m, const std::array<char, 4>& mpid,
                             std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, AddOrder::kWireSizeMpid), AddOrder::kTypeMpid, m.hdr);
  store_be64(p + 11, m.order_ref);
  p[19] = static_cast<std::byte>(m.side);
  store_be32(p + 20, m.shares);
  std::memset(p + 24, ' ', 8);
  store_be32(p + 32, m.price);
  detail::put_chars(p + 36, mpid.data(), mpid.size());
}

inline void encode(const OrderExecuted& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, OrderExecuted::kWireSize), OrderExecuted::kType, m.hdr);
  store_be64(p + 11, m.order_ref);
  store_be32(p + 19, m.executed_shares);
  store_be64(p + 23, m.match_number);
}

inline void encode(const OrderExecutedWithPrice& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, OrderExecutedWithPrice::kWireSize),
                                    OrderExecutedWithPrice::kType, m.hdr);
  store_be64(p + 11, m.order_ref);
  store_be32(p + 19, m.executed_shares);
  store_be64(p + 23, m.match_number);
  p[31] = static_cast<std::byte>(m.printable);
  store_be32(p + 32, m.execution_price);
}

inline void encode(const OrderCancel& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, OrderCancel::kWireSize), OrderCancel::kType, m.hdr);
  store_be64(p + 11, m.order_ref);
  store_be32(p + 19, m.cancelled_shares);
}

inline void encode(const OrderDelete& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, OrderDelete::kWireSize), OrderDelete::kType, m.hdr);
  store_be64(p + 11, m.order_ref);
}

inline void encode(const OrderReplace& m, std::vector<std::byte>& out) {
  std::byte* p = detail::put_header(detail::grow(out, OrderReplace::kWireSize), OrderReplace::kType, m.hdr);
  store_be64(p + 11, m.original_ref);
  store_be64(p + 19, m.new_ref);
  store_be32(p + 27, m.shares);
  store_be32(p + 31, m.price);
}

// Message with its 2-byte length prefix, as in the BinaryFILE sample files.
template <typename M>
void encode_framed(const M& m, std::vector<std::byte>& out) {
  store_be16(detail::grow(out, 2), static_cast<std::uint16_t>(M::kWireSize));
  encode(m, out);
}

}  // namespace hft::itch
