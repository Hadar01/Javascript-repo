#include "hft/itch/parser.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cstddef>
#include <initializer_list>
#include <variant>
#include <vector>

#include "hft/itch/encoder.hpp"

namespace {

using namespace hft::itch;
using hft::Side;

using AnyMessage = std::variant<SystemEvent, StockDirectory, AddOrder, OrderExecuted,
                                OrderExecutedWithPrice, OrderCancel, OrderDelete, OrderReplace>;

// Records every decoded message. One template on() covers every type in the
// variant.
struct Recorder {
  std::vector<AnyMessage> got;
  template <typename M>
  void on(const M& m) {
    got.emplace_back(m);
  }
};

// Handles adds only: everything else must be skipped at compile time.
struct AddsOnly {
  int adds = 0;
  void on(const AddOrder&) { ++adds; }
};

std::vector<std::byte> raw(std::initializer_list<unsigned> v) {
  std::vector<std::byte> out;
  for (unsigned x : v) out.push_back(static_cast<std::byte>(x));
  return out;
}

template <typename M>
M parse_one(const std::vector<std::byte>& bytes) {
  Recorder r;
  EXPECT_EQ(parse_message(bytes, r), ParseStatus::Ok);
  EXPECT_EQ(r.got.size(), 1u);
  return std::get<M>(r.got.at(0));
}

constexpr Header kHdr{.locate = 7, .tracking = 3, .timestamp = 34'200'123'456'789};

// Written byte by byte from the spec, not produced by our encoder. A
// round-trip test can't catch a wrong offset that the encoder and parser
// share: both would agree and both would be wrong. This one can.
TEST(Parser, AddOrderFromSpecBytes) {
  const auto bytes = raw({
      'A',                                       // type
      0x00, 0x07,                                // stock locate = 7
      0x00, 0x03,                                // tracking number = 3
      0x1F, 0x1A, 0x0D, 0x48, 0x8B, 0x15,        // timestamp (6 bytes)
      0, 0, 0, 0, 0, 0, 0x30, 0x39,              // order ref = 12345
      'S',                                       // side
      0x00, 0x00, 0x01, 0x2C,                    // shares = 300
      'A', 'A', 'P', 'L', ' ', ' ', ' ', ' ',    // stock
      0x00, 0x1C, 0x9C, 0x38,                    // price = 1875000 ($187.50)
  });
  ASSERT_EQ(bytes.size(), AddOrder::kWireSize);
  const auto m = parse_one<AddOrder>(bytes);
  EXPECT_EQ(m.hdr.locate, 7);
  EXPECT_EQ(m.hdr.tracking, 3);
  EXPECT_EQ(m.hdr.timestamp, 0x1F1A0D488B15ull);
  EXPECT_EQ(m.order_ref, 12345u);
  EXPECT_EQ(m.side, Side::Sell);
  EXPECT_EQ(m.shares, 300u);
  EXPECT_EQ(m.price, 1'875'000u);
}

TEST(Parser, ReplaceFromSpecBytes) {
  const auto bytes = raw({
      'U', 0x00, 0x01, 0x00, 0x00, 0, 0, 0, 0, 0, 1,  // header, timestamp = 1
      0, 0, 0, 0, 0, 0, 0, 10,                        // original ref = 10
      0, 0, 0, 0, 0, 0, 0, 11,                        // new ref = 11
      0x00, 0x00, 0x00, 0x64,                         // shares = 100
      0x00, 0x0F, 0x42, 0x40,                         // price = 1000000 ($100)
  });
  ASSERT_EQ(bytes.size(), OrderReplace::kWireSize);
  const auto m = parse_one<OrderReplace>(bytes);
  EXPECT_EQ(m.original_ref, 10u);
  EXPECT_EQ(m.new_ref, 11u);
  EXPECT_EQ(m.shares, 100u);
  EXPECT_EQ(m.price, 1'000'000u);
}

// Encode, parse back, compare every field (operator== is defaulted).
template <typename M>
void expect_round_trip(const M& m) {
  std::vector<std::byte> buf;
  encode(m, buf);
  ASSERT_EQ(buf.size(), M::kWireSize);
  EXPECT_EQ(parse_one<M>(buf), m);
}

TEST(Parser, RoundTripsEveryMessageType) {
  expect_round_trip(SystemEvent{.hdr = kHdr, .event_code = 'Q'});
  expect_round_trip(StockDirectory{.hdr = kHdr, .stock = {'M', 'S', 'F', 'T', ' ', ' ', ' ', ' '}});
  expect_round_trip(AddOrder{.hdr = kHdr, .order_ref = 99, .side = Side::Buy, .shares = 500, .price = 4'210'000});
  expect_round_trip(OrderExecuted{.hdr = kHdr, .order_ref = 99, .executed_shares = 200, .match_number = 5});
  expect_round_trip(OrderExecutedWithPrice{.hdr = kHdr, .order_ref = 99, .executed_shares = 1,
                                           .match_number = 6, .printable = 'N', .execution_price = 4'200'000});
  expect_round_trip(OrderCancel{.hdr = kHdr, .order_ref = 99, .cancelled_shares = 50});
  expect_round_trip(OrderDelete{.hdr = kHdr, .order_ref = 99});
  expect_round_trip(OrderReplace{.hdr = kHdr, .original_ref = 99, .new_ref = 100, .shares = 300, .price = 4'220'000});
}

TEST(Parser, AddWithMpidDecodesAsAddOrder) {
  const AddOrder add{.hdr = kHdr, .order_ref = 1, .side = Side::Sell, .shares = 100, .price = 10'000};
  std::vector<std::byte> buf;
  encode_with_mpid(add, {'G', 'S', 'C', 'O'}, buf);
  ASSERT_EQ(buf.size(), AddOrder::kWireSizeMpid);
  EXPECT_EQ(parse_one<AddOrder>(buf), add);
}

TEST(Parser, TooShortIsMalformedAndNotDelivered) {
  std::vector<std::byte> buf;
  encode(OrderDelete{.hdr = kHdr, .order_ref = 1}, buf);
  buf.pop_back();
  Recorder r;
  EXPECT_EQ(parse_message(buf, r), ParseStatus::Malformed);
  EXPECT_TRUE(r.got.empty());
  EXPECT_EQ(parse_message(std::span<const std::byte>{}, r), ParseStatus::Malformed);
}

TEST(Parser, FTruncatedToAddLengthIsMalformed) {
  // An 'F' needs 40 bytes, even though 36 would be a whole 'A'.
  std::vector<std::byte> buf;
  encode_with_mpid(AddOrder{.hdr = kHdr, .order_ref = 1, .side = Side::Buy, .shares = 1, .price = 1}, {'A', 'B', 'C', 'D'},
                   buf);
  buf.resize(AddOrder::kWireSize);
  Recorder r;
  EXPECT_EQ(parse_message(buf, r), ParseStatus::Malformed);
}

TEST(Parser, BadSideIsMalformed) {
  std::vector<std::byte> buf;
  encode(AddOrder{.hdr = kHdr, .order_ref = 1, .side = Side::Buy, .shares = 1, .price = 1}, buf);
  buf[19] = std::byte{'X'};
  Recorder r;
  EXPECT_EQ(parse_message(buf, r), ParseStatus::Malformed);
  EXPECT_TRUE(r.got.empty());
}

TEST(Parser, LongerThanSpecIsAccepted) {
  // Extra trailing bytes (a future spec revision adding a field) are ignored.
  std::vector<std::byte> buf;
  const OrderDelete d{.hdr = kHdr, .order_ref = 42};
  encode(d, buf);
  buf.push_back(std::byte{0});
  EXPECT_EQ(parse_one<OrderDelete>(buf), d);
}

TEST(Parser, UnknownTypeIsSkipped) {
  Recorder r;
  const auto bytes = raw({'P', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0});
  EXPECT_EQ(parse_message(bytes, r), ParseStatus::UnknownType);
  EXPECT_TRUE(r.got.empty());
}

TEST(Parser, HandlerOnlyGetsTypesItHandles) {
  std::vector<std::byte> buf;
  encode_framed(SystemEvent{.hdr = kHdr, .event_code = 'O'}, buf);
  encode_framed(AddOrder{.hdr = kHdr, .order_ref = 1, .side = Side::Buy, .shares = 1, .price = 1}, buf);
  encode_framed(OrderDelete{.hdr = kHdr, .order_ref = 1}, buf);
  AddsOnly h;
  const FeedStats s = parse_binary_file(buf, h);
  EXPECT_EQ(h.adds, 1);
  EXPECT_EQ(s.messages, 3u);
  EXPECT_EQ(s.unknown_type, 0u);  // known types the handler ignores aren't "unknown"
}

TEST(Parser, FramingWalksAllMessages) {
  std::vector<std::byte> buf;
  for (hft::OrderRef ref = 1; ref <= 100; ++ref) {
    encode_framed(AddOrder{.hdr = kHdr, .order_ref = ref, .side = Side::Buy, .shares = 1, .price = 1}, buf);
    encode_framed(OrderDelete{.hdr = kHdr, .order_ref = ref}, buf);
  }
  Recorder r;
  const FeedStats s = parse_binary_file(buf, r);
  EXPECT_EQ(s.messages, 200u);
  EXPECT_EQ(s.bytes_consumed, buf.size());
  EXPECT_EQ(s.trailing_bytes, 0u);
  ASSERT_EQ(r.got.size(), 200u);
  EXPECT_EQ(std::get<OrderDelete>(r.got.back()).order_ref, 100u);
}

TEST(Parser, TruncatedTailIsReportedNotParsed) {
  std::vector<std::byte> buf;
  encode_framed(OrderDelete{.hdr = kHdr, .order_ref = 1}, buf);
  const std::size_t whole = buf.size();
  encode_framed(OrderDelete{.hdr = kHdr, .order_ref = 2}, buf);
  // Cut every possible number of bytes off the second message.
  for (std::size_t cut = 1; cut < 2 + OrderDelete::kWireSize; ++cut) {
    const std::span<const std::byte> part(buf.data(), buf.size() - cut);
    Recorder r;
    const FeedStats s = parse_binary_file(part, r);
    EXPECT_EQ(s.messages, 1u) << "cut " << cut;
    EXPECT_EQ(s.bytes_consumed, whole) << "cut " << cut;
    EXPECT_EQ(s.trailing_bytes, part.size() - whole) << "cut " << cut;
  }
}

TEST(Parser, ZeroLengthMessageIsMalformedAndSkipped) {
  std::vector<std::byte> buf = raw({0x00, 0x00});
  encode_framed(OrderDelete{.hdr = kHdr, .order_ref = 9}, buf);
  Recorder r;
  const FeedStats s = parse_binary_file(buf, r);
  EXPECT_EQ(s.messages, 2u);
  EXPECT_EQ(s.malformed, 1u);
  ASSERT_EQ(r.got.size(), 1u);
  EXPECT_EQ(std::get<OrderDelete>(r.got[0]).order_ref, 9u);
}

}  // namespace
