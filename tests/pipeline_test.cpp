// The feed thread and the strategy thread running for real, connected by
// the ring. Under TSan this checks that the whole handoff (start handshake,
// ring, shutdown flag, final drain) is free of data races.

#include "hft/feed/pipeline.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>
#include <vector>

#include "hft/itch/synthetic.hpp"

namespace {

using hft::feed::BookUpdate;
using hft::feed::FeedHandler;
using hft::feed::OnFull;
using hft::feed::UpdateRing;

// Records what the strategy thread saw. Plain fields: only the strategy
// thread writes them, and the test reads them after run_pipeline returns
// (the thread has been joined by then, which synchronises).
struct Recorder {
  std::vector<BookUpdate> latest;  // last update per symbol
  std::uint64_t received = 0;
  std::uint64_t gaps = 0;
  std::uint64_t out_of_order = 0;
  std::uint64_t next_seq = 0;
  int slow_spins = 0;  // > 0 makes the strategy slow, to fill the ring

  void operator()(const BookUpdate& u) {
    if (u.seq < next_seq) ++out_of_order;
    if (u.seq > next_seq) gaps += u.seq - next_seq;
    next_seq = u.seq + 1;
    ++received;
    for (int i = 0; i < slow_spins; ++i) hft::cpu_relax();
    for (auto& l : latest) {
      if (l.locate == u.locate) {
        l = u;
        return;
      }
    }
    latest.push_back(u);
  }

  const BookUpdate* find(hft::Locate locate) const {
    for (const auto& l : latest) {
      if (l.locate == locate) return &l;
    }
    return nullptr;
  }
};

const std::vector<std::byte>& feed() {
  static const auto f = hft::itch::make_synthetic_feed(
      {.symbols = 6, .messages = 200'000, .target_live_orders = 3'000, .max_level_offset = 24, .seed = 11});
  return f;
}

struct Rig {
  std::unique_ptr<UpdateRing> ring = std::make_unique<UpdateRing>();
  std::unique_ptr<FeedHandler> handler;
  Recorder recorder;

  explicit Rig(OnFull policy) {
    handler = std::make_unique<FeedHandler>(
        hft::feed::FeedHandlerConfig{.book = {.max_orders = 8'192, .levels_per_side = 64}, .on_full = policy}, *ring);
    for (const char* s : {"SYN0", "SYN2", "SYN4"}) handler->subscribe_ticker(s);
    recorder.latest.reserve(3);
  }
};

TEST(Pipeline, WaitPolicyDeliversEveryUpdateInOrder) {
  Rig s(OnFull::Wait);
  const auto result = hft::feed::run_pipeline(feed(), *s.handler, *s.ring, s.recorder);

  EXPECT_EQ(result.feed.messages, 200'000u + 1 + 6);
  const auto& pub = s.handler->stats();
  EXPECT_GT(pub.published, 0u);
  EXPECT_EQ(pub.dropped, 0u);
  EXPECT_EQ(s.recorder.received, pub.published);
  EXPECT_EQ(s.recorder.gaps, 0u);
  EXPECT_EQ(s.recorder.out_of_order, 0u);

  // Nothing was lost, so the strategy's last view of each symbol must be
  // exactly the feed thread's final book.
  for (const char* sym : {"SYN0", "SYN2", "SYN4"}) {
    const auto loc = s.handler->book().find_locate(sym);
    ASSERT_TRUE(loc.has_value()) << sym;
    const BookUpdate* seen = s.recorder.find(*loc);
    ASSERT_NE(seen, nullptr) << sym;
    EXPECT_TRUE(hft::feed::same_levels(*seen, s.handler->snapshot(*loc))) << sym;
  }
}

// With the drop policy, how many updates get dropped depends on timing. What
// must hold regardless: every drop the feed counted is visible to the
// strategy, either as a gap in the sequence, or (for drops after the last
// update it received) as the difference between the last sequence number
// it saw and the number of updates the feed attempted.
TEST(Pipeline, DropPolicyGapsMatchDrops) {
  Rig s(OnFull::Drop);
  s.recorder.slow_spins = 200;  // a slow strategy makes the ring fill up
  hft::feed::run_pipeline(feed(), *s.handler, *s.ring, s.recorder);

  const auto& pub = s.handler->stats();
  const std::uint64_t attempted = pub.published + pub.dropped;
  const std::uint64_t dropped_at_end = attempted - s.recorder.next_seq;
  EXPECT_EQ(s.recorder.received, pub.published);
  EXPECT_EQ(s.recorder.gaps + dropped_at_end, pub.dropped);
  EXPECT_EQ(s.recorder.out_of_order, 0u);
}

}  // namespace
