#include "hft/net/sequence_tracker.hpp"

#include <gtest/gtest.h>

#include <cstdint>

namespace {

using hft::net::SequenceTracker;

TEST(SequenceTracker, InOrderPacketsAreAllNew) {
  SequenceTracker t;
  EXPECT_EQ(t.accept(1, 3), 0);
  EXPECT_EQ(t.accept(4, 2), 0);
  EXPECT_EQ(t.expected(), 6u);
  EXPECT_EQ(t.stats().gap_events, 0u);
  EXPECT_EQ(t.stats().duplicate_packets, 0u);
}

TEST(SequenceTracker, ForwardJumpIsAGap) {
  SequenceTracker t;
  (void)t.accept(1, 3);                  // messages 1-3
  EXPECT_EQ(t.accept(10, 2), 0);         // 4-9 never arrived
  EXPECT_EQ(t.stats().gap_events, 1u);
  EXPECT_EQ(t.stats().gap_messages, 6u);
  EXPECT_EQ(t.expected(), 12u);
}

TEST(SequenceTracker, RepeatedPacketIsSkippedEntirely) {
  SequenceTracker t;
  (void)t.accept(1, 3);
  EXPECT_EQ(t.accept(1, 3), 3);  // skip all three
  EXPECT_EQ(t.stats().duplicate_packets, 1u);
  EXPECT_EQ(t.expected(), 4u);
}

TEST(SequenceTracker, PartialOverlapSkipsOnlyTheOldPart) {
  SequenceTracker t;
  (void)t.accept(1, 3);           // 1-3
  EXPECT_EQ(t.accept(2, 4), 2);   // 2-5: skip 2 and 3, deliver 4 and 5
  EXPECT_EQ(t.stats().overlap_packets, 1u);
  EXPECT_EQ(t.expected(), 6u);
}

TEST(SequenceTracker, LatePacketAfterAGapIsDropped) {
  // The tracker only moves forward: a packet that arrives after the gap was
  // declared is treated as old. Ordering packets well is the receiver's job.
  SequenceTracker t;
  (void)t.accept(1, 1);
  (void)t.accept(3, 1);
  EXPECT_EQ(t.accept(2, 1), 1);
  EXPECT_EQ(t.stats().gap_messages, 1u);
}

TEST(SequenceTracker, HeartbeatRevealsLossAtTheEndOfABurst) {
  SequenceTracker t;
  (void)t.accept(1, 5);           // 1-5
  EXPECT_EQ(t.accept(8, 0), 0);   // heartbeat: "next is 8", so 6 and 7 were lost
  EXPECT_EQ(t.stats().gap_messages, 2u);
  EXPECT_EQ(t.accept(8, 0), 0);   // a repeated heartbeat is not a duplicate packet
  EXPECT_EQ(t.stats().duplicate_packets, 0u);
}

TEST(SequenceTracker, LostFirstPacketIsAGapWhenTheStartIsKnown) {
  SequenceTracker t(/*first_seq=*/1);
  EXPECT_EQ(t.accept(4, 2), 0);  // packet with messages 1-3 never arrived
  EXPECT_EQ(t.stats().gap_messages, 3u);
}

TEST(SequenceTracker, JoiningMidStreamIsNotAGap) {
  SequenceTracker t;
  EXPECT_EQ(t.accept(1000, 2), 0);
  EXPECT_EQ(t.stats().gap_events, 0u);
  EXPECT_EQ(t.expected(), 1002u);
}

// A/B arbitration, simulated: 20,000 packets of 3 messages each, every
// packet sent on line A then line B, each line losing ~5% independently.
// Messages are lost only where BOTH lines lost the packet.
TEST(SequenceTracker, ArbitrationLosesOnlyPacketsBothLinesLost) {
  std::uint64_t rng = 99;
  auto lost = [&rng] {  // xorshift; ~5% true
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng % 100 < 5;
  };
  SequenceTracker t(1);
  std::uint64_t both_lost_messages = 0;
  std::uint64_t seq = 1;
  for (int i = 0; i < 20'000; ++i, seq += 3) {
    const bool a_lost = lost();
    const bool b_lost = lost();
    // Braces matter: EXPECT_EQ expands to an if/else of its own, so as the
    // unbraced body of an `if` its `else` would be ambiguous (-Wdangling-else).
    if (!a_lost) {
      EXPECT_EQ(t.accept(seq, 3), 0);
    }
    if (!b_lost) {
      EXPECT_EQ(t.accept(seq, 3), a_lost ? 0 : 3);  // second copy: all old
    }
    if (a_lost && b_lost) both_lost_messages += 3;
  }
  (void)t.accept(seq, 0);  // end-of-session heartbeat: reveals loss at the tail too
  EXPECT_GT(both_lost_messages, 0u);
  EXPECT_EQ(t.stats().gap_messages, both_lost_messages);
}

}  // namespace
