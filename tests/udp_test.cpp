// The network path over real UDP sockets on this machine: a sender thread
// packs a synthetic feed into MoldUDP64 packets, the receiver rebuilds the
// book from them, and the result is compared with the book built straight
// from the file.
//
// Unicast on 127.0.0.1 works everywhere, so most tests use it, and they
// bind to port 0 so the kernel picks free ports. The multicast test skips
// itself when the machine can't loop multicast back to itself.
//
// The whole feed (~600 KB) fits in the receiver's socket buffer, so the
// sender can go flat out without the kernel dropping anything: every loss
// in these tests is a loss the test chose.

#include <gtest/gtest.h>

#include <array>
#include <chrono>
#include <cstring>
#include <memory>
#include <optional>
#include <thread>
#include <vector>

#include "hft/book/market_book.hpp"
#include "hft/itch/framing.hpp"
#include "hft/itch/parser.hpp"
#include "hft/itch/synthetic.hpp"
#include "hft/net/mold_receiver.hpp"
#include "hft/net/moldudp64.hpp"
#include "hft/net/udp_socket.hpp"

namespace {

using namespace hft;
using net::Endpoint;
using net::UdpSocket;

constexpr std::uint16_t kSymbols = 4;
constexpr std::uint64_t kOrderMessages = 20'000;

const std::vector<std::byte>& feed() {
  static const auto f = itch::make_synthetic_feed(
      {.symbols = kSymbols, .messages = kOrderMessages, .target_live_orders = 1'000, .max_level_offset = 16, .seed = 5});
  return f;
}

struct SendResult {
  std::uint64_t packets = 0;
  std::array<std::uint64_t, 2> dropped_messages{};  // per line
  std::uint64_t both_dropped_messages = 0;          // lost on every line
};

// Sends the whole feed to each endpoint; drop(line, packet_index) chooses
// which packets each line "loses". Ends with three end-of-session packets.
template <typename Drop>
SendResult send_feed(const std::vector<Endpoint>& lines, Drop drop) {
  UdpSocket sock = UdpSocket::open_sender();
  std::vector<sockaddr_in> dest;
  for (const auto& e : lines) dest.push_back(e.to_sockaddr());
  net::Session session;
  std::memcpy(session.data(), "TESTSESS01", session.size());
  net::PacketBuilder builder(session, 1372);
  SendResult r;

  auto flush = [&] {
    if (builder.empty()) return;
    const std::uint16_t count = builder.count();
    const auto packet = builder.finish();
    bool lost_everywhere = true;
    for (std::size_t l = 0; l < dest.size(); ++l) {
      if (drop(l, r.packets)) {
        r.dropped_messages[l] += count;
      } else {
        EXPECT_TRUE(sock.send_to(packet, dest[l]));
        lost_everywhere = false;
      }
    }
    if (lost_everywhere) r.both_dropped_messages += count;
    ++r.packets;
  };
  itch::for_each_framed(feed(), [&](std::span<const std::byte> m) {
    if (!builder.fits(m.size())) flush();
    builder.add(m);
  });
  flush();
  for (int i = 0; i < 3; ++i) {
    for (const auto& d : dest) sock.send_to(builder.control(net::kMoldEndOfSession), d);
  }
  return r;
}

// Every level of every symbol must match.
void expect_same_books(const book::MarketBook& got, const book::MarketBook& want) {
  for (Locate loc = 1; loc <= kSymbols; ++loc) {
    for (Side side : {Side::Buy, Side::Sell}) {
      ASSERT_EQ(got.book(loc).depth(side), want.book(loc).depth(side)) << "locate " << loc;
      for (std::size_t d = 0; d < want.book(loc).depth(side); ++d) {
        ASSERT_EQ(*got.book(loc).level(side, d), *want.book(loc).level(side, d)) << "locate " << loc;
      }
    }
  }
}

const book::MarketBook& truth() {
  static const auto b = [] {
    auto mb = std::make_unique<book::MarketBook>(book::MarketBookConfig{.max_orders = 8'192, .levels_per_side = 32});
    itch::parse_binary_file(feed(), *mb);
    return mb;
  }();
  return *b;
}

struct Received {
  std::unique_ptr<book::MarketBook> book =
      std::make_unique<book::MarketBook>(book::MarketBookConfig{.max_orders = 8'192, .levels_per_side = 32});
  net::ReceiverStats stats;
};

// Opens the receive sockets first (UDP keeps nothing for sockets that don't
// exist yet), starts the sender on another thread, then receives here.
template <typename Drop>
std::pair<Received, SendResult> round_trip(std::vector<Endpoint> lines, Drop drop, int window_us = 100'000) {
  std::vector<UdpSocket> socks;
  for (auto& e : lines) {
    socks.push_back(UdpSocket::open_receiver(e, 4 << 20));
    if (!e.is_multicast()) e.port = socks.back().local_port();  // bound to port 0: learn the real one
  }
  std::vector<UdpSocket*> ptrs;
  for (auto& s : socks) ptrs.push_back(&s);

  SendResult sent;
  std::thread sender([&] { sent = send_feed(lines, drop); });
  Received got;
  auto receiver = std::make_unique<net::MoldReceiver>(
      net::ReceiverConfig{.idle_timeout_ms = 2000, .start_timeout_ms = 5000, .arbitration_window_us = window_us});
  got.stats = receiver->run(std::span<UdpSocket* const>(ptrs), *got.book);
  sender.join();
  return {std::move(got), sent};
}

constexpr auto kNoLoss = [](std::size_t, std::uint64_t) { return false; };

TEST(Udp, SingleLineDeliversTheWholeFeed) {
  auto [got, sent] = round_trip({Endpoint::parse("127.0.0.1:0")}, kNoLoss);
  EXPECT_TRUE(got.stats.end_of_session);
  EXPECT_EQ(got.stats.packets[0], sent.packets + 1);  // + the end-of-session packet
  EXPECT_EQ(got.stats.sequence.gap_events, 0u);
  EXPECT_EQ(got.stats.itch.messages, kOrderMessages + 1 + kSymbols);
  expect_same_books(*got.book, truth());
}

TEST(Udp, LostPacketsAreCountedExactly) {
  auto drop = [](std::size_t, std::uint64_t i) { return i % 7 == 3; };
  auto [got, sent] = round_trip({Endpoint::parse("127.0.0.1:0")}, drop);
  EXPECT_TRUE(got.stats.end_of_session);
  EXPECT_GT(sent.dropped_messages[0], 0u);
  EXPECT_EQ(got.stats.sequence.gap_messages, sent.dropped_messages[0]);
  EXPECT_EQ(got.stats.itch.messages + sent.dropped_messages[0], kOrderMessages + 1 + kSymbols);
  // Lost deletes and adds leave the book wrong, and it says so.
  const auto& b = got.book->stats();
  EXPECT_GT(b.unknown_order + b.duplicate_order + b.overfill, 0u);
}

TEST(Udp, ArbitrationRecoversEveryPacketOneLineLost) {
  // Never the same packet on both lines: arbitration must hide every loss.
  auto drop = [](std::size_t line, std::uint64_t i) { return line == 0 ? i % 5 == 0 : i % 5 == 2; };
  auto [got, sent] = round_trip({Endpoint::parse("127.0.0.1:0"), Endpoint::parse("127.0.0.1:0")}, drop);
  EXPECT_GT(sent.dropped_messages[0], 0u);
  EXPECT_GT(sent.dropped_messages[1], 0u);
  EXPECT_EQ(sent.both_dropped_messages, 0u);
  EXPECT_EQ(got.stats.sequence.gap_events, 0u);
  EXPECT_GT(got.stats.sequence.duplicate_packets, 0u);  // second copies, discarded
  expect_same_books(*got.book, truth());
}

TEST(Udp, ArbitrationLosesOnlyPacketsBothLinesLost) {
  // Both lines lose every 12th packet; each also loses others on its own.
  auto drop = [](std::size_t line, std::uint64_t i) { return line == 0 ? i % 4 == 0 : i % 6 == 0; };
  auto [got, sent] = round_trip({Endpoint::parse("127.0.0.1:0"), Endpoint::parse("127.0.0.1:0")}, drop);
  EXPECT_GT(sent.both_dropped_messages, 0u);
  EXPECT_EQ(got.stats.sequence.gap_messages, sent.both_dropped_messages);
}

// Can this machine send multicast to itself? Containers and some CI
// machines can't (no multicast route, or the interface lacks MULTICAST).
bool multicast_loopback_works(const Endpoint& group) {
  try {
    UdpSocket rx = UdpSocket::open_receiver(group, 1 << 16);
    UdpSocket tx = UdpSocket::open_sender();
    const std::array<std::byte, 4> probe{};
    if (!tx.send_to(probe, group.to_sockaddr())) return false;
    std::array<std::byte, 64> buf{};
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(300);
    while (std::chrono::steady_clock::now() < deadline) {
      if (rx.try_recv(buf) > 0) return true;
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  } catch (const std::exception&) {
  }
  return false;
}

TEST(Udp, MulticastDeliversTheWholeFeed) {
  const Endpoint group = Endpoint::parse("239.255.77.1:39077");
  if (!multicast_loopback_works(group)) GTEST_SKIP() << "multicast loopback not available on this machine";
  auto [got, sent] = round_trip({group}, kNoLoss);
  EXPECT_TRUE(got.stats.end_of_session);
  EXPECT_EQ(got.stats.sequence.gap_events, 0u);
  expect_same_books(*got.book, truth());
}

}  // namespace
