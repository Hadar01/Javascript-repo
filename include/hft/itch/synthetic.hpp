#pragma once

// Synthetic ITCH 5.0 feed generator.
//
// It produces a valid BinaryFILE stream (system event, stock directory, then
// a random mix of add / execute / cancel / delete / replace) with a stable
// number of live orders. The message mix and sizes are roughly like real
// Nasdaq data, but each symbol's mid price is fixed, so the book's
// economics are not. Use it for tests, benchmarks and demos without the
// sample files, and never for training the model.
//
// It is deterministic: the same config gives the same bytes on every
// machine and compiler (it uses its own RNG, not std:: distributions, whose
// output differs between standard libraries).

#include <cstddef>
#include <cstdint>
#include <vector>

namespace hft::itch {

struct SyntheticFeedConfig {
  std::uint16_t symbols = 8;
  std::uint64_t messages = 1'000'000;      // order messages, excluding setup
  std::uint32_t target_live_orders = 4'000;
  std::uint32_t max_level_offset = 32;      // ticks from mid; bounds book depth
  std::uint64_t seed = 1;
};

[[nodiscard]] std::vector<std::byte> make_synthetic_feed(const SyntheticFeedConfig& cfg);

}  // namespace hft::itch
