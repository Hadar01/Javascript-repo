#include "hft/net/moldudp64.hpp"

#include <gtest/gtest.h>

#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>

namespace {

using namespace hft::net;

Session session(const char* s) {
  Session out;
  std::memcpy(out.data(), s, out.size());
  return out;
}

std::vector<std::byte> bytes(std::initializer_list<unsigned> v) {
  std::vector<std::byte> out;
  for (unsigned x : v) out.push_back(static_cast<std::byte>(x));
  return out;
}

std::vector<std::byte> text(const std::string& s) {
  std::vector<std::byte> out;
  for (char c : s) out.push_back(static_cast<std::byte>(c));
  return out;
}

std::vector<std::string> messages_of(std::span<const std::byte> packet, std::uint16_t count, bool* ok = nullptr) {
  std::vector<std::string> out;
  const bool good = for_each_message(packet, count, [&](std::span<const std::byte> m) {
    out.emplace_back(reinterpret_cast<const char*>(m.data()), m.size());
  });
  if (ok != nullptr) *ok = good;
  return out;
}

// Written from the specification, not from the builder.
TEST(MoldUdp64, HeaderFromSpecBytes) {
  const auto packet = bytes({'H', 'F', 'T', 'L', 'O', 'B', '0', '0', '0', '1',  // session
                             0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,  // sequence
                             0x00, 0x02,                                      // count = 2
                             0x00, 0x01, 'A',                                 // message 1: "A"
                             0x00, 0x02, 'B', 'C'});                          // message 2: "BC"
  const auto h = decode_header(packet);
  ASSERT_TRUE(h.has_value());
  EXPECT_EQ(std::string(h->session.data(), 10), "HFTLOB0001");
  EXPECT_EQ(h->seq, 0x0102030405060708u);
  EXPECT_EQ(h->count, 2);
  EXPECT_EQ(messages_of(packet, h->count), (std::vector<std::string>{"A", "BC"}));
}

TEST(MoldUdp64, ShortPacketHasNoHeader) {
  EXPECT_FALSE(decode_header(std::vector<std::byte>(19)).has_value());
  EXPECT_TRUE(decode_header(std::vector<std::byte>(20)).has_value());
}

TEST(MoldUdp64, BuilderRoundTripAndSequenceAdvance) {
  PacketBuilder b(session("SESSION001"), 1400, /*first_seq=*/1);
  for (const char* m : {"one", "two", "three"}) b.add(text(m));
  const auto p1 = b.finish();
  const auto h1 = decode_header(p1);
  ASSERT_TRUE(h1.has_value());
  EXPECT_EQ(h1->seq, 1u);
  EXPECT_EQ(h1->count, 3);
  EXPECT_EQ(messages_of(p1, h1->count), (std::vector<std::string>{"one", "two", "three"}));
  EXPECT_EQ(p1.size(), 20u + (2 + 3) + (2 + 3) + (2 + 5));

  b.add(text("four"));
  const auto h2 = decode_header(b.finish());
  EXPECT_EQ(h2->seq, 4u);  // 1 + 3 messages
  EXPECT_EQ(h2->count, 1);
  EXPECT_EQ(b.next_seq(), 5u);
}

TEST(MoldUdp64, FitsRespectsMaxPayload) {
  PacketBuilder b(session("SESSION001"), /*max_payload=*/20 + 2 + 10);
  EXPECT_TRUE(b.fits(10));
  EXPECT_FALSE(b.fits(11));
  b.add(text("0123456789"));
  EXPECT_FALSE(b.fits(0));  // even an empty message needs its 2-byte length
}

TEST(MoldUdp64, HeartbeatAndEndOfSession) {
  PacketBuilder b(session("SESSION001"), 1400, 42);
  const auto hb = decode_header(b.control(kMoldHeartbeat));
  EXPECT_EQ(hb->seq, 42u);  // the next message to come
  EXPECT_EQ(hb->count, 0);
  const auto eos = decode_header(b.control(kMoldEndOfSession));
  EXPECT_EQ(eos->count, 0xFFFF);
  EXPECT_EQ(b.next_seq(), 42u);  // control packets carry no messages
}

TEST(MoldUdp64, BlockRunningPastTheEndIsMalformed) {
  // Claims a 5-byte message but only 2 bytes follow.
  auto packet = std::vector<std::byte>(20);
  for (auto x : bytes({0x00, 0x05, 'a', 'b'})) packet.push_back(x);
  bool ok = true;
  EXPECT_TRUE(messages_of(packet, 1, &ok).empty());
  EXPECT_FALSE(ok);
}

TEST(MoldUdp64, CountLargerThanBlocksPresentIsMalformed) {
  PacketBuilder b(session("SESSION001"), 1400);
  b.add(text("x"));
  b.add(text("y"));
  const auto p = b.finish();
  bool ok = true;
  EXPECT_EQ(messages_of(p, 3, &ok).size(), 2u);  // delivers what is there, then reports the problem
  EXPECT_FALSE(ok);
}

TEST(MoldUdp64, ForEachMessageRejectsPacketShorterThanHeader) {
  bool ok = true;
  EXPECT_TRUE(messages_of(std::vector<std::byte>(5), 1, &ok).empty());
  EXPECT_FALSE(ok);
}

}  // namespace
