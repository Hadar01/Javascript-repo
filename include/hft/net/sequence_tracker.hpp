#pragma once

// SequenceTracker: decides, per packet, which messages are new.
//
// UDP can lose, duplicate and reorder packets. MoldUDP64 numbers every
// message, so the receiver tracks the next sequence it expects:
//
//   packet ends at or before `expected`  -> duplicate: skip all of it
//   packet starts after `expected`       -> gap: messages were lost. Count
//                                           them and accept the packet
//   packet starts before `expected` but  -> overlap: skip the messages
//   ends after it                           already seen, accept the rest
//
// The same logic does A/B line arbitration. The exchange sends identical
// packets on two multicast groups (separate network paths). The receiver
// listens to both and keeps whichever copy arrives first; the second copy is
// a duplicate. A message is lost only if BOTH lines lose it.
//
// The tracker declares a gap as soon as it is shown a later packet. Feeding
// it packets in the right order across the two lines is the receiver's job
// (see MoldReceiver: lowest sequence first, plus a short wait for the other
// line before a gap is accepted).

#include <cstdint>

namespace hft::net {

struct SequenceStats {
  std::uint64_t duplicate_packets = 0;  // nothing new in them
  std::uint64_t overlap_packets = 0;    // partly new
  std::uint64_t gap_events = 0;         // times the sequence jumped forward
  std::uint64_t gap_messages = 0;       // messages never received
};

class SequenceTracker {
 public:
  // first_seq: the sequence the stream starts at, if known. MoldUDP64
  // sessions start at 1, so a receiver listening before the session begins
  // should pass 1. Otherwise a lost FIRST packet goes unnoticed: whatever
  // arrives first would be taken as the start. 0 means "joining mid-stream":
  // the first packet seen defines the start.
  explicit SequenceTracker(std::uint64_t first_seq = 0) noexcept
      : started_(first_seq != 0), expected_(first_seq) {}

  // A packet carrying messages seq .. seq+count-1 (count 0 for a heartbeat,
  // whose seq is the next message to come). Returns how many leading
  // messages to skip; equal to count means "nothing new".
  [[nodiscard]] std::uint16_t accept(std::uint64_t seq, std::uint16_t count) noexcept {
    if (!started_) {
      // Joining mid-stream: whatever arrives first defines the start.
      started_ = true;
      expected_ = seq;
    }
    const std::uint64_t end = seq + count;
    if (seq > expected_) {
      ++stats_.gap_events;
      stats_.gap_messages += seq - expected_;
      expected_ = end;
      return 0;
    }
    if (end <= expected_) {
      if (count > 0) ++stats_.duplicate_packets;
      return count;
    }
    const auto skip = static_cast<std::uint16_t>(expected_ - seq);
    if (skip > 0) ++stats_.overlap_packets;
    expected_ = end;
    return skip;
  }

  [[nodiscard]] bool started() const noexcept { return started_; }
  [[nodiscard]] std::uint64_t expected() const noexcept { return expected_; }
  [[nodiscard]] const SequenceStats& stats() const noexcept { return stats_; }

 private:
  bool started_ = false;
  std::uint64_t expected_ = 0;
  SequenceStats stats_;
};

}  // namespace hft::net
