#pragma once

// run_pipeline: the two-thread setup.
//
//   calling thread (feed)       strategy thread
//   parse ITCH -> MarketBook    pop BookUpdate -> consume(update)
//            \--- SpscRing<BookUpdate> ---/
//
// The strategy thread busy-polls the ring: no sleeping and no condition
// variable, because waking a sleeping thread costs microseconds. That
// burns a whole core, which is why each thread gets its own pinned core.
//
// Startup: the feed waits for the strategy thread to say it is ready.
// Shutdown: when the feed is exhausted, the feed thread sets `done`
// (release). The strategy thread, once it sees `done` (acquire), drains
// what is left and exits. The release/acquire pair guarantees every update
// pushed before `done` was set is visible to the drain.

#include <atomic>
#include <cstddef>
#include <span>
#include <thread>

#include "hft/common/cpu.hpp"
#include "hft/feed/feed_handler.hpp"
#include "hft/itch/parser.hpp"

namespace hft::feed {

struct PipelineConfig {
  int feed_cpu = -1;      // -1: don't pin
  int strategy_cpu = -1;
};

struct PipelineResult {
  itch::FeedStats feed;
  bool feed_pinned = false;
  bool strategy_pinned = false;
};

// Runs the feed on the calling thread and `consume(const BookUpdate&)` on a
// new thread. Returns after the strategy thread has processed every update.
// Note: pinning the calling thread is not undone afterwards.
template <typename Consumer>
PipelineResult run_pipeline(std::span<const std::byte> feed, FeedHandler& handler, UpdateRing& ring,
                            Consumer& consume, const PipelineConfig& cfg = {}) {
  PipelineResult result;
  // `done` gets a cache-line block of its own. The strategy thread reads it
  // every time the ring is empty. Unpadded, it sat on the same line as the
  // FeedStats the parser updates on every message, and each update dragged
  // that line away from the polling core: the feed ran at 595 ns/msg
  // instead of 104 (measured; see LEARNING.md, stage 2).
  CachePadded<std::atomic<bool>> done;
  // Start handshake: the feed waits until the strategy thread is running on
  // its core. Creating a thread and moving it to another core can take a
  // millisecond or more, and every update published meanwhile would sit in
  // the ring, polluting the latency tail with a one-off startup cost.
  CachePadded<std::atomic<bool>> ready;
  std::atomic<bool> strategy_pinned{false};

  // std::jthread (C++20) joins in its destructor, so an early return or an
  // exception can't leave a running thread behind (std::thread would call
  // std::terminate instead).
  std::jthread strategy([&] {
    strategy_pinned.store(pin_current_thread(cfg.strategy_cpu), std::memory_order_relaxed);
    ready.value.store(true, std::memory_order_release);
    BookUpdate u;
    while (true) {
      if (ring.try_pop(u)) {
        consume(u);
        continue;
      }
      if (done.value.load(std::memory_order_acquire)) {
        while (ring.try_pop(u)) consume(u);  // whatever was pushed before `done`
        return;
      }
      cpu_relax();
    }
  });

  result.feed_pinned = pin_current_thread(cfg.feed_cpu);
  while (!ready.value.load(std::memory_order_acquire)) cpu_relax();
  result.feed = itch::parse_binary_file(feed, handler);
  done.value.store(true, std::memory_order_release);
  strategy.join();
  result.strategy_pinned = strategy_pinned.load(std::memory_order_relaxed);
  return result;
}

}  // namespace hft::feed
