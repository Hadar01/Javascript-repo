#include "hft/concurrency/spsc_ring.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <cstdint>
#include <memory>
#include <thread>

namespace {

using hft::SpscRing;

TEST(SpscRing, EmptyRingPopsNothing) {
  SpscRing<int, 8> ring;
  int v = 0;
  EXPECT_FALSE(ring.try_pop(v));
  EXPECT_EQ(ring.size_approx(), 0u);
}

TEST(SpscRing, HoldsExactlyCapacityItems) {
  // Counters that never wrap mean no slot is sacrificed to tell full from empty.
  SpscRing<int, 8> ring;
  for (int i = 0; i < 8; ++i) EXPECT_TRUE(ring.try_push(i)) << i;
  EXPECT_FALSE(ring.try_push(99));
  EXPECT_EQ(ring.size_approx(), 8u);
}

TEST(SpscRing, FifoOrder) {
  SpscRing<int, 8> ring;
  for (int i = 0; i < 5; ++i) ASSERT_TRUE(ring.try_push(i));
  for (int i = 0; i < 5; ++i) {
    int v = -1;
    ASSERT_TRUE(ring.try_pop(v));
    EXPECT_EQ(v, i);
  }
  int v = 0;
  EXPECT_FALSE(ring.try_pop(v));
}

TEST(SpscRing, FullThenOneFreeSlot) {
  SpscRing<int, 4> ring;
  for (int i = 0; i < 4; ++i) ASSERT_TRUE(ring.try_push(i));
  int v = 0;
  ASSERT_TRUE(ring.try_pop(v));
  EXPECT_EQ(v, 0);
  // The producer's cached copy of the consumer's index still says "full".
  // try_push must re-read the real index before giving up.
  EXPECT_TRUE(ring.try_push(4));
  EXPECT_FALSE(ring.try_push(5));
}

TEST(SpscRing, WrapsAroundManyTimes) {
  SpscRing<std::uint64_t, 8> ring;
  std::uint64_t next_in = 0;
  std::uint64_t next_out = 0;
  // Uneven batch sizes so the indices cross the end of the buffer at every
  // possible offset.
  for (int round = 0; round < 1000; ++round) {
    const int batch = 1 + round % 8;
    for (int i = 0; i < batch; ++i) ASSERT_TRUE(ring.try_push(next_in++));
    for (int i = 0; i < batch; ++i) {
      std::uint64_t v = 0;
      ASSERT_TRUE(ring.try_pop(v));
      ASSERT_EQ(v, next_out++);
    }
  }
}

// Two fields that must agree. If the consumer ever read a slot that was
// still being written, or a stale one, they'd disagree.
struct Item {
  std::uint64_t seq;
  std::uint64_t check;
};
constexpr std::uint64_t check_of(std::uint64_t seq) { return seq * 0x9E3779B97F4A7C15ULL; }

// Two real threads, a tiny ring (so it is full or empty most of the time and
// both cached-index refresh paths run constantly), a million items. The
// consumer checks every item arrives once, in order, intact. Under TSan this
// also checks the memory ordering: a missing release/acquire is a data race
// on the slot.
TEST(SpscRing, TwoThreadsTransferEveryItemInOrder) {
  constexpr std::uint64_t kItems = 1'000'000;
  auto ring = std::make_unique<SpscRing<Item, 16>>();

  std::uint64_t received = 0;
  std::uint64_t errors = 0;
  std::thread consumer([&] {
    Item it{};
    while (received < kItems) {
      if (!ring->try_pop(it)) {
        hft::cpu_relax();
        continue;
      }
      if (it.seq != received || it.check != check_of(it.seq)) ++errors;
      ++received;
    }
  });

  for (std::uint64_t i = 0; i < kItems; ++i) {
    const Item it{.seq = i, .check = check_of(i)};
    while (!ring->try_push(it)) hft::cpu_relax();
  }
  consumer.join();  // join() is a synchronisation point: we may now read received/errors

  EXPECT_EQ(received, kItems);
  EXPECT_EQ(errors, 0u);
}

}  // namespace

// ---------------------------------------------------------------------------
// Proof that the memory ordering matters (ThreadSanitizer builds only).
//
// BrokenRing is SpscRing with every release/acquire replaced by relaxed. On
// x86 it would probably pass the stress test above: x86 rarely reorders
// stores. But in the C++ memory model, relaxed atomics create no
// happens-before edge, so the slot write and the slot read are a data race,
// which is undefined behaviour. The compiler may legally reorder them, and an
// ARM CPU will. TSan checks the memory model, not the hardware, so it
// reports the race.
// ---------------------------------------------------------------------------
#if defined(__SANITIZE_THREAD__)
#define HFT_HAS_TSAN 1
#elif defined(__has_feature)
#if __has_feature(thread_sanitizer)
#define HFT_HAS_TSAN 1
#endif
#endif

#if defined(HFT_HAS_TSAN)
extern "C" const char* __tsan_default_options() { return "halt_on_error=1"; }
#endif

namespace {

template <typename T, std::size_t N>
class BrokenRing {
 public:
  bool try_push(const T& v) {
    const auto w = write_.load(std::memory_order_relaxed);
    if (w - read_.load(std::memory_order_relaxed) == N) return false;
    slots_[w % N] = v;
    write_.store(w + 1, std::memory_order_relaxed);  // BUG: should be release
    return true;
  }
  bool try_pop(T& out) {
    const auto r = read_.load(std::memory_order_relaxed);
    if (r == write_.load(std::memory_order_relaxed)) return false;  // BUG: should be acquire
    out = slots_[r % N];
    read_.store(r + 1, std::memory_order_relaxed);
    return true;
  }

 private:
  std::atomic<std::uint64_t> write_{0};
  std::atomic<std::uint64_t> read_{0};
  std::uint64_t slots_[N] = {};
};

[[maybe_unused]] volatile std::uint64_t g_sink = 0;

[[maybe_unused]] void run_broken_ring() {
  BrokenRing<std::uint64_t, 16> ring;
  std::uint64_t sum = 0;
  std::thread consumer([&] {
    std::uint64_t v = 0;
    for (int got = 0; got < 1000;) {
      if (ring.try_pop(v)) {
        sum += v;  // use the value: if it were never used, the compiler would
        ++got;     // delete the slot read, and with it the race TSan should see
      }
    }
  });
  for (std::uint64_t i = 0; i < 1000; ++i) {
    while (!ring.try_push(i)) {
    }
  }
  consumer.join();
  g_sink = sum;
}

TEST(SpscRingMemoryOrder, TsanCatchesRelaxedPublish) {
#if !defined(HFT_HAS_TSAN)
  GTEST_SKIP() << "not a TSan build";
#else
  // The body is a separate function because EXPECT_DEATH is a macro: the
  // comma in BrokenRing<std::uint64_t, 16> would split its arguments.
  EXPECT_DEATH(run_broken_ring(), "data race");
#endif
}

}  // namespace
