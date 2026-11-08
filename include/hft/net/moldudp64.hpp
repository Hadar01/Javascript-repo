#pragma once

// MoldUDP64: how Nasdaq actually sends ITCH over UDP multicast.
//
// Downstream packet:
//   @0   session          10 bytes, ASCII. Identifies the stream for the day.
//   @10  sequence number   8 bytes, big-endian. Sequence of the FIRST message.
//   @18  message count     2 bytes, big-endian.
//   @20  message blocks: [2-byte big-endian length][message], count times.
//
// Message sequence numbers start at 1 and increase by one per message, so a
// packet with sequence s and count n carries messages s .. s+n-1, and the
// next packet should start at s+n. That is how a receiver detects loss.
//
//   count 0       heartbeat: sent while idle. Its sequence is the NEXT
//                 message to come, so a heartbeat also reveals messages
//                 lost at the end of a burst.
//   count 0xFFFF  end of session.
//
// Real deployments also run a request server for retransmitting lost
// messages; this project detects and counts loss but doesn't recover it.

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <optional>
#include <span>
#include <vector>

#include "hft/itch/wire.hpp"

namespace hft::net {

inline constexpr std::size_t kMoldHeaderSize = 20;
inline constexpr std::uint16_t kMoldHeartbeat = 0;
inline constexpr std::uint16_t kMoldEndOfSession = 0xFFFF;

// Largest UDP payload that fits one Ethernet frame without IP fragmentation:
// MTU 1500 - 20 (IP header) - 8 (UDP header) = 1472. A fragmented datagram
// is lost if ANY fragment is lost, so feeds never fragment. This container's
// MTU is 1400, so the apps default to 1372; pass the right value for yours.
inline constexpr std::size_t kMaxPayloadMtu1500 = 1472;

using Session = std::array<char, 10>;

struct MoldHeader {
  Session session;
  std::uint64_t seq;
  std::uint16_t count;
};

[[nodiscard]] inline std::optional<MoldHeader> decode_header(std::span<const std::byte> packet) noexcept {
  if (packet.size() < kMoldHeaderSize) return std::nullopt;
  MoldHeader h{};
  std::memcpy(h.session.data(), packet.data(), h.session.size());
  h.seq = itch::load_be64(packet.data() + 10);
  h.count = itch::load_be16(packet.data() + 18);
  return h;
}

// Calls f(std::span<const std::byte> message) for each of the `count`
// message blocks after the header. Returns false, having stopped early, if a
// block runs past the end of the packet. Every length comes from the
// network: nothing in it may be trusted to stay in bounds.
template <typename F>
bool for_each_message(std::span<const std::byte> packet, std::uint16_t count, F&& f) {
  std::size_t off = kMoldHeaderSize;
  const std::size_t size = packet.size();
  if (size < kMoldHeaderSize) return false;
  for (std::uint16_t i = 0; i < count; ++i) {
    if (size - off < 2) return false;
    const std::size_t len = itch::load_be16(packet.data() + off);
    if (size - off - 2 < len) return false;
    f(packet.subspan(off + 2, len));
    off += 2 + len;
  }
  return true;
}

// Builds packets one at a time into a buffer allocated once.
//   add() as many messages as fit, then finish() returns the packet bytes
//   and advances the sequence number by the number of messages sent.
class PacketBuilder {
 public:
  PacketBuilder(const Session& session, std::size_t max_payload, std::uint64_t first_seq = 1)
      : buf_(std::max(max_payload, kMoldHeaderSize)), next_seq_(first_seq) {
    std::memcpy(buf_.data(), session.data(), session.size());
  }

  [[nodiscard]] bool fits(std::size_t message_len) const noexcept {
    return count_ < kMoldEndOfSession - 1 && buf_.size() - size_ >= 2 + message_len;
  }
  [[nodiscard]] bool empty() const noexcept { return count_ == 0; }
  [[nodiscard]] std::uint16_t count() const noexcept { return count_; }
  [[nodiscard]] std::uint64_t next_seq() const noexcept { return next_seq_; }

  // Precondition: fits(message.size()).
  void add(std::span<const std::byte> message) noexcept {
    itch::store_be16(buf_.data() + size_, static_cast<std::uint16_t>(message.size()));
    std::memcpy(buf_.data() + size_ + 2, message.data(), message.size());
    size_ += 2 + message.size();
    ++count_;
  }

  // The finished packet. Valid until the next add() or finish().
  [[nodiscard]] std::span<const std::byte> finish() noexcept {
    write_header(next_seq_, count_);
    const std::span<const std::byte> packet(buf_.data(), size_);
    next_seq_ += count_;
    size_ = kMoldHeaderSize;
    count_ = 0;
    return packet;
  }

  // A heartbeat or end-of-session packet: header only. Doesn't touch any
  // messages added so far (call it only when empty()).
  [[nodiscard]] std::span<const std::byte> control(std::uint16_t count) noexcept {
    write_header(next_seq_, count);
    return {buf_.data(), kMoldHeaderSize};
  }

 private:
  void write_header(std::uint64_t seq, std::uint16_t count) noexcept {
    itch::store_be64(buf_.data() + 10, seq);
    itch::store_be16(buf_.data() + 18, count);
  }

  std::vector<std::byte> buf_;
  std::size_t size_ = kMoldHeaderSize;
  std::uint16_t count_ = 0;
  std::uint64_t next_seq_;
};

}  // namespace hft::net
