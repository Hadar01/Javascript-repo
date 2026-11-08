#pragma once

// Walk a BinaryFILE buffer ([2-byte big-endian length][message]...) and hand
// each raw message to a callback, without parsing it. The replay server uses
// this to repackage messages into network packets.
// (parse_binary_file in parser.hpp does the same walk and parses as it goes.)

#include <cstddef>
#include <span>

#include "hft/itch/wire.hpp"

namespace hft::itch {

// Calls f(std::span<const std::byte> message) for each complete message.
// Returns the number of bytes consumed; an incomplete last message is left
// unconsumed, exactly as in parse_binary_file.
template <typename F>
std::size_t for_each_framed(std::span<const std::byte> buf, F&& f) {
  const std::byte* const data = buf.data();
  const std::size_t size = buf.size();
  std::size_t off = 0;
  while (size - off >= 2) {
    const std::size_t len = load_be16(data + off);
    if (size - off - 2 < len) break;
    f(std::span<const std::byte>(data + off + 2, len));
    off += 2 + len;
  }
  return off;
}

}  // namespace hft::itch
