#pragma once

// Reading and writing big-endian integers at arbitrary byte offsets.
//
// ITCH fields are big-endian and sit at odd offsets (a 4-byte price at
// offset 32 of a message that itself starts anywhere in the file). The
// tempting code is
//
//     auto v = *reinterpret_cast<const std::uint32_t*>(p);   // DON'T
//
// which is undefined behaviour twice over: p may not be 4-byte aligned, and
// it reads bytes through a uint32_t lvalue (a "strict aliasing" violation).
// It usually works on x86 until the optimiser relies on the rule.
//
// std::memcpy into a local is the defined way to do it, and it costs
// nothing: GCC and Clang turn a fixed-size memcpy into a single load
// instruction (x86 allows unaligned loads), followed by one BSWAP.

#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace hft::itch {

static_assert(std::endian::native == std::endian::little,
              "the byte swaps below assume a little-endian host");

[[nodiscard]] inline std::uint16_t load_be16(const std::byte* p) noexcept {
  std::uint16_t v;
  std::memcpy(&v, p, sizeof v);
  return __builtin_bswap16(v);
}

[[nodiscard]] inline std::uint32_t load_be32(const std::byte* p) noexcept {
  std::uint32_t v;
  std::memcpy(&v, p, sizeof v);
  return __builtin_bswap32(v);
}

[[nodiscard]] inline std::uint64_t load_be64(const std::byte* p) noexcept {
  std::uint64_t v;
  std::memcpy(&v, p, sizeof v);
  return __builtin_bswap64(v);
}

// ITCH timestamps are 6 bytes. Read the 2 high bytes and the 4 low bytes and
// combine them. Never read 8 bytes here: the last 2 would belong to the next
// field, or lie past the end of the buffer.
[[nodiscard]] inline std::uint64_t load_be48(const std::byte* p) noexcept {
  return (std::uint64_t{load_be16(p)} << 32) | load_be32(p + 2);
}

inline void store_be16(std::byte* p, std::uint16_t v) noexcept {
  v = __builtin_bswap16(v);
  std::memcpy(p, &v, sizeof v);
}

inline void store_be32(std::byte* p, std::uint32_t v) noexcept {
  v = __builtin_bswap32(v);
  std::memcpy(p, &v, sizeof v);
}

inline void store_be64(std::byte* p, std::uint64_t v) noexcept {
  v = __builtin_bswap64(v);
  std::memcpy(p, &v, sizeof v);
}

inline void store_be48(std::byte* p, std::uint64_t v) noexcept {
  store_be16(p, static_cast<std::uint16_t>(v >> 32));
  store_be32(p + 2, static_cast<std::uint32_t>(v));
}

}  // namespace hft::itch
