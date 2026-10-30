#include "hft/itch/wire.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cstddef>
#include <cstdint>

namespace {

using namespace hft::itch;

template <std::size_t N>
std::array<std::byte, N> bytes(const std::array<unsigned, N>& v) {
  std::array<std::byte, N> out{};
  for (std::size_t i = 0; i < N; ++i) out[i] = static_cast<std::byte>(v[i]);
  return out;
}

TEST(Wire, LoadsBigEndian) {
  const auto b = bytes<8>({0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08});
  EXPECT_EQ(load_be16(b.data()), 0x0102u);
  EXPECT_EQ(load_be32(b.data()), 0x01020304u);
  EXPECT_EQ(load_be48(b.data()), 0x010203040506ull);
  EXPECT_EQ(load_be64(b.data()), 0x0102030405060708ull);
}

// Every ITCH field after the type byte sits at an odd or otherwise
// unaligned offset. The loads must work at all of them (and UBSan's
// alignment check in the asan build would flag a cast-based load here).
TEST(Wire, LoadsAtUnalignedOffsets) {
  const auto b = bytes<12>({0xAA, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x11, 0x22, 0x33});
  EXPECT_EQ(load_be16(b.data() + 1), 0x1234u);
  EXPECT_EQ(load_be32(b.data() + 1), 0x12345678u);
  EXPECT_EQ(load_be32(b.data() + 3), 0x56789ABCu);
  EXPECT_EQ(load_be48(b.data() + 1), 0x123456789ABCull);
  EXPECT_EQ(load_be64(b.data() + 3), 0x56789ABCDEF01122ull);
}

TEST(Wire, Load48UsesOnlySixBytes) {
  // The bytes after the 6-byte field must not leak into the value.
  const auto b = bytes<8>({0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xFF, 0xFF});
  EXPECT_EQ(load_be48(b.data()), 1u);
}

TEST(Wire, StoreThenLoadRoundTrips) {
  std::array<std::byte, 16> b{};
  store_be16(b.data() + 1, 0xBEEF);
  store_be32(b.data() + 3, 0xDEADBEEF);
  store_be48(b.data() + 7, 0x0000'FFFF'0000'1234ull);
  EXPECT_EQ(load_be16(b.data() + 1), 0xBEEFu);
  EXPECT_EQ(load_be32(b.data() + 3), 0xDEADBEEFu);
  EXPECT_EQ(load_be48(b.data() + 7), 0x0000'FFFF'0000'1234ull);
  // store_be16 must write the high byte first.
  EXPECT_EQ(b[1], std::byte{0xBE});
  EXPECT_EQ(b[2], std::byte{0xEF});
}

TEST(Wire, MaxTimestamp) {
  // The latest possible ITCH timestamp: just under 24h in ns, which needs
  // 47 bits. A 32-bit variable would wrap after 4.29 s.
  constexpr std::uint64_t kEndOfDay = 86'400'000'000'000ull - 1;
  std::array<std::byte, 6> b{};
  store_be48(b.data(), kEndOfDay);
  EXPECT_EQ(load_be48(b.data()), kEndOfDay);
}

}  // namespace
