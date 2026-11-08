#pragma once

// MoldReceiver: the network thread's loop.
//
//   poll each line (non-blocking recv) -> one waiting packet per line
//     -> process the packet with the LOWEST sequence number first
//     -> SequenceTracker (drop duplicates, count gaps)
//     -> each new message -> itch::parse_message -> handler.on(msg)
//
// It busy-polls: try_recv returns at once when nothing is waiting, and the
// loop spins. A blocking recv would put the thread to sleep, and the
// kernel's wake-up adds microseconds to every packet (bench/udp_bench.cpp
// measures it). The cost is one core at 100%.
//
// A/B arbitration is a merge of two sequenced streams. Each line holds at
// most one waiting packet; the one with the lower sequence goes first. If
// processing it would open a gap and the other line has nothing waiting
// yet, the receiver gives that line `arbitration_window_us` to deliver the
// missing packet before declaring the gap. Without that wait, a packet that
// line A lost but line B was just about to deliver would be declared lost,
// and B's copy then discarded as old (measured: 99 gaps instead of ~18 with
// 1% independent loss per line). With a single line it never waits.
//
// It stops at the first end-of-session packet (the server repeats it, in
// case one copy is lost), after `idle_timeout_ms` without packets once data
// has started flowing, after `start_timeout_ms` if nothing ever arrives, or
// when `stop` is set.

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <span>

#include "hft/common/cpu.hpp"
#include "hft/itch/parser.hpp"
#include "hft/net/moldudp64.hpp"
#include "hft/net/sequence_tracker.hpp"
#include "hft/net/udp_socket.hpp"

namespace hft::net {

struct ReceiverConfig {
  int idle_timeout_ms = 2000;      // stop after this long without packets, once data has flowed
  int start_timeout_ms = 0;        // give up waiting for the first packet; 0 = wait forever
  int arbitration_window_us = 50;  // A/B only: how long to wait for the other line to fill a gap
  std::uint64_t first_seq = 1;     // the session starts here; 0 = joining mid-stream
};

struct ReceiverStats {
  std::array<std::uint64_t, 2> packets{};  // per line
  std::uint64_t heartbeats = 0;
  std::uint64_t malformed_packets = 0;      // too short, truncated, or blocks overrunning
  std::uint64_t arbitration_waits = 0;      // a gap was about to open: waited for the other line
  std::uint64_t arbitration_timeouts = 0;   // ... and the other line didn't deliver in time
  bool end_of_session = false;
  bool idle_timeout = false;
  SequenceStats sequence;
  itch::FeedStats itch;  // messages delivered to the ITCH parser
};

class MoldReceiver {
 public:
  // Holds two 64 KB packet buffers: allocate it with make_unique, not on a stack.
  explicit MoldReceiver(const ReceiverConfig& cfg = {}) : cfg_(cfg), tracker_(cfg.first_seq) {}

  // lines: one socket, or two for A/B arbitration.
  template <typename Handler>
  ReceiverStats run(std::span<UdpSocket* const> lines, Handler& handler, const std::atomic<bool>* stop = nullptr) {
    using clock = std::chrono::steady_clock;
    ReceiverStats stats;
    const std::size_t n_lines = lines.size() < 2 ? lines.size() : 2;
    const auto window = std::chrono::microseconds(cfg_.arbitration_window_us);
    const auto run_start = clock::now();
    auto idle_since = run_start;
    auto wait_start = run_start;
    bool waiting = false;
    bool started = false;
    std::uint64_t idle_spins = 0;

    while (stop == nullptr || !stop->load(std::memory_order_relaxed)) {
      // 1. Give every line with an empty slot a chance to deliver a packet.
      for (std::size_t l = 0; l < n_lines; ++l) {
        if (!slot_[l].full) fill(slot_[l], *lines[l], stats.packets[l], stats);
      }

      // 2. Pick the waiting packet with the lowest sequence number.
      int pick = -1;
      for (std::size_t l = 0; l < n_lines; ++l) {
        if (slot_[l].full && (pick < 0 || slot_[l].seq < slot_[static_cast<std::size_t>(pick)].seq)) {
          pick = static_cast<int>(l);
        }
      }

      if (pick < 0) {
        // Nothing waiting on any line.
        cpu_relax();
        // Reading the clock costs ~25 ns, so the timeouts are checked only
        // every 64k empty polls (a few milliseconds).
        if ((++idle_spins & 0xFFFF) != 0) continue;
        const auto now = clock::now();
        if (idle_spins == 0x10000) idle_since = now;  // first check of this quiet spell
        const bool timed_out = started ? now - idle_since > std::chrono::milliseconds(cfg_.idle_timeout_ms)
                                       : cfg_.start_timeout_ms > 0 &&
                                             now - run_start > std::chrono::milliseconds(cfg_.start_timeout_ms);
        if (timed_out) {
          stats.idle_timeout = true;
          break;
        }
        continue;
      }
      idle_spins = 0;
      started = true;
      Slot& s = slot_[static_cast<std::size_t>(pick)];

      // 3. Would this packet open a gap while the other line might still
      //    fill it? Then wait, briefly, for the other line.
      if (n_lines == 2 && tracker_.started() && s.seq > tracker_.expected() &&
          !slot_[static_cast<std::size_t>(1 - pick)].full) {
        const auto now = clock::now();
        if (!waiting) {
          waiting = true;
          wait_start = now;
          ++stats.arbitration_waits;
        }
        if (now - wait_start < window) continue;  // keep polling both lines
        ++stats.arbitration_timeouts;             // the other line lost it too: a real gap
      }
      waiting = false;

      s.full = false;
      if (handle_packet(std::span<const std::byte>(s.buf.data(), s.len), handler, stats)) break;  // end of session
    }
    stats.sequence = tracker_.stats();
    return stats;
  }

  [[nodiscard]] const SequenceTracker& tracker() const noexcept { return tracker_; }

 private:
  // One packet received from a line but not yet processed. 64 KB is the
  // largest UDP payload, so no valid datagram is ever truncated.
  struct Slot {
    std::array<std::byte, 65536> buf;
    std::size_t len = 0;
    std::uint64_t seq = 0;  // 0 for a packet too short to have a header: processed first, counted malformed
    bool full = false;
  };

  static void fill(Slot& slot, UdpSocket& sock, std::uint64_t& packets, ReceiverStats& stats) noexcept {
    const std::ptrdiff_t n = sock.try_recv(slot.buf);
    if (n <= 0) return;
    ++packets;
    if (static_cast<std::size_t>(n) > slot.buf.size()) {
      ++stats.malformed_packets;  // truncated
      return;
    }
    slot.len = static_cast<std::size_t>(n);
    const auto hdr = decode_header(std::span<const std::byte>(slot.buf.data(), slot.len));
    slot.seq = hdr ? hdr->seq : 0;
    slot.full = true;
  }

  // Returns true at end of session.
  template <typename Handler>
  bool handle_packet(std::span<const std::byte> packet, Handler& handler, ReceiverStats& stats) {
    const auto hdr = decode_header(packet);
    if (!hdr) [[unlikely]] {
      ++stats.malformed_packets;
      return false;
    }
    if (hdr->count == kMoldEndOfSession) {
      // Its sequence is the next message that would have come, so it
      // reveals messages lost at the very end of the stream.
      (void)tracker_.accept(hdr->seq, 0);
      stats.end_of_session = true;
      return true;
    }
    const std::uint16_t skip = tracker_.accept(hdr->seq, hdr->count);
    if (hdr->count == kMoldHeartbeat) {
      ++stats.heartbeats;
      return false;
    }
    std::uint16_t index = 0;
    const bool ok = for_each_message(packet, hdr->count, [&](std::span<const std::byte> msg) {
      if (index++ < skip) return;  // already delivered from the other line
      ++stats.itch.messages;
      switch (itch::parse_message(msg, handler)) {
        case itch::ParseStatus::Ok:
          break;
        case itch::ParseStatus::UnknownType:
          ++stats.itch.unknown_type;
          break;
        case itch::ParseStatus::Malformed:
          ++stats.itch.malformed;
          break;
      }
    });
    if (!ok) [[unlikely]] ++stats.malformed_packets;
    return false;
  }

  ReceiverConfig cfg_;
  SequenceTracker tracker_;
  std::array<Slot, 2> slot_{};
};

}  // namespace hft::net
