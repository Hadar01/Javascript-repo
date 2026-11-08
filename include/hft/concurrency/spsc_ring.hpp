#pragma once

// SpscRing: a bounded, lock-free, single-producer / single-consumer queue.
//
// Exactly one thread may call try_push() and exactly one (other) thread may
// call try_pop(). With that restriction no compare-and-swap is needed: each
// index has exactly one writer, so plain atomic loads and stores are enough.
//
// Design:
//   - Capacity is a compile-time power of two. `index & (N - 1)` picks the
//     slot with an AND of a constant instead of a division.
//   - write_ and read_ count up forever and are never wrapped. full is
//     `write - read == N`, empty is `write == read`. Wrapping indices would
//     make full and empty look the same unless one slot is always kept
//     free. At 1e9 operations per second, 64 bits last 584 years.
//   - Release/acquire ordering is what makes the data visible:
//       producer: write the slot, then store write_ with RELEASE
//       consumer: load write_ with ACQUIRE, then read the slot
//     A release store and an acquire load that reads its value create a
//     "happens-before" edge: every write before the release is visible
//     after the acquire. The same pairing in the other direction (consumer
//     releases read_, producer acquires it) guarantees the consumer has
//     finished reading a slot before the producer overwrites it.
//   - Each thread's fields live on their own 128-byte-aligned block, so
//     the producer writing write_ never invalidates the line holding read_
//     (false sharing).
//   - Each side keeps a private cached copy of the other side's index and
//     re-reads the shared atomic only when the cache says "full" (producer)
//     or "empty" (consumer). Every read of the other side's index pulls a
//     cache line across cores; with the cache, that happens once per
//     batch instead of once per item.
//
// T must be trivially copyable: slots are plain assignments, with no
// constructors or destructors to run. Our messages are plain structs.
//
// The ring stores its slots inline, so a large one is a large object.
// Allocate it once at startup (std::make_unique), not on a thread's stack.

#include <array>
#include <atomic>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <type_traits>

#include "hft/common/cpu.hpp"

namespace hft {

template <typename T, std::size_t N>
class SpscRing {
  static_assert(std::has_single_bit(N), "capacity must be a power of two");
  static_assert(std::is_trivially_copyable_v<T>, "slots are copied with plain assignment");
  static_assert(std::atomic<std::uint64_t>::is_always_lock_free,
                "a lock-based atomic would make this ring lock-based too");

 public:
  static constexpr std::size_t kCapacity = N;

  SpscRing() = default;
  // The two threads hold references to one ring. Copying or moving it while
  // they run would be meaningless, so it is pinned in place.
  SpscRing(const SpscRing&) = delete;
  SpscRing& operator=(const SpscRing&) = delete;

  // Producer thread only. Returns false if the ring is full.
  [[nodiscard]] bool try_push(const T& value) noexcept {
    // Our own index: only this thread writes it, so a relaxed load is enough.
    const std::uint64_t w = producer_.write.load(std::memory_order_relaxed);
    if (w - producer_.read_cache == N) {
      // Looks full. Refresh our view of the consumer (one cross-core read).
      // ACQUIRE: pairs with the consumer's release store of read_, so its
      // reads of the slot we're about to overwrite are already complete.
      producer_.read_cache = consumer_.read.load(std::memory_order_acquire);
      if (w - producer_.read_cache == N) return false;
    }
    slots_[w & kMask] = value;
    // RELEASE: the slot write above becomes visible no later than the new
    // index. Without it, the consumer could see the index and read a slot
    // that hasn't been written yet (the compiler or CPU may reorder).
    producer_.write.store(w + 1, std::memory_order_release);
    return true;
  }

  // Consumer thread only. Returns false if the ring is empty.
  [[nodiscard]] bool try_pop(T& out) noexcept {
    const std::uint64_t r = consumer_.read.load(std::memory_order_relaxed);
    if (r == consumer_.write_cache) {
      // Looks empty. ACQUIRE: pairs with the producer's release store, so
      // the slot contents written before it are visible to us.
      consumer_.write_cache = producer_.write.load(std::memory_order_acquire);
      if (r == consumer_.write_cache) return false;
    }
    out = slots_[r & kMask];
    // RELEASE: our read of the slot completes before the producer can see
    // the slot as free and overwrite it.
    consumer_.read.store(r + 1, std::memory_order_release);
    return true;
  }

  // An instantaneous estimate from either thread. The other side may have
  // moved by the time the caller looks at it, so never base a decision on it.
  [[nodiscard]] std::size_t size_approx() const noexcept {
    const std::uint64_t w = producer_.write.load(std::memory_order_acquire);
    const std::uint64_t r = consumer_.read.load(std::memory_order_acquire);
    return w >= r ? static_cast<std::size_t>(w - r) : 0;
  }

 private:
  static constexpr std::uint64_t kMask = N - 1;

  // Written by the producer. read_cache is the producer's private copy of
  // consumer_.read; it shares the producer's line because only the
  // producer touches it.
  struct alignas(kNoFalseSharing) ProducerSide {
    std::atomic<std::uint64_t> write{0};
    std::uint64_t read_cache = 0;
  };
  // Written by the consumer; write_cache mirrors producer_.write.
  struct alignas(kNoFalseSharing) ConsumerSide {
    std::atomic<std::uint64_t> read{0};
    std::uint64_t write_cache = 0;
  };

  ProducerSide producer_;
  ConsumerSide consumer_;
  // Starts on its own block too, so neither index shares a line with slot 0.
  alignas(kNoFalseSharing) std::array<T, N> slots_{};
};

}  // namespace hft
