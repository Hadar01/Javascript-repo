#pragma once

// MeasuringConsumer: the stage 2/3 stand-in for a strategy.
//
// It does what every consumer must do (check sequence numbers, keep the
// latest book per symbol) plus measures how long each update took to cross
// the ring. Stage 4 replaces the "strategy" part with features and a model.

#include <cstdint>
#include <vector>

#include "hft/common/cpu.hpp"
#include "hft/common/latency_recorder.hpp"
#include "hft/feed/book_update.hpp"

namespace hft::feed {

struct MeasuringConsumer {
  LatencyRecorder& latency;
  std::vector<BookUpdate> latest;  // last update per symbol; reserve() it up front
  std::uint64_t received = 0;
  std::uint64_t gaps = 0;        // updates the feed dropped (ring full)
  std::uint64_t clock_skew = 0;  // receive TSC earlier than publish TSC
  std::uint64_t next_seq = 0;

  void operator()(const BookUpdate& u) noexcept {
    const std::uint64_t now = rdtsc();
    // The TSCs of different cores are synchronised on this hardware; if a
    // reading ever went backwards, count it instead of recording a huge
    // bogus latency.
    if (now >= u.publish_tsc) {
      latency.record(now - u.publish_tsc);
    } else {
      ++clock_skew;
    }
    if (u.seq != next_seq) gaps += u.seq - next_seq;
    next_seq = u.seq + 1;
    ++received;
    for (auto& l : latest) {
      if (l.locate == u.locate) {
        l = u;
        return;
      }
    }
    if (latest.size() < latest.capacity()) latest.push_back(u);  // never reallocates
  }

  [[nodiscard]] const BookUpdate* find(Locate locate) const noexcept {
    for (const auto& l : latest) {
      if (l.locate == locate) return &l;
    }
    return nullptr;
  }
};

}  // namespace hft::feed
