#pragma once

// Synthetic ITCH 5.0 feed generator.
//
// It produces a valid BinaryFILE stream (system event, stock directory, then
// a random mix of add / execute / cancel / delete / replace) with a stable
// number of live orders. The message mix and sizes are roughly like real
// Nasdaq data. By default each symbol's prices are centred on a fixed mid,
// so the book's economics are not realistic. Use it for tests, benchmarks
// and demos without the sample files.
//
// It is deterministic: the same config gives the same bytes on every
// machine and compiler (it uses its own RNG, not std:: distributions, whose
// output differs between standard libraries).
//
// trending = true adds price dynamics, for training models (stage 4):
//   - Each symbol is in a hidden "up" or "down" regime that occasionally flips.
//   - Prices move one tick at a time: a move up executes every resting ask at
//     the new centre (an aggressive buyer lifting the offers), then quotes
//     re-form around the new centre. 80% of moves follow the regime; 20% go
//     the other way, as noise.
//   - Order flow leaks the regime: new orders lean toward the regime's side.
// So order-flow features and recent moves predict the next move, as they
// do (far more weakly) in real markets. The rules are known, so a model's
// accuracy can be checked against them. Nothing about real markets is
// learned from it.

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
  bool trending = false;
  double move_prob = 0.02;            // per message: a one-tick move of one symbol
  double regime_flip_prob = 0.0005;   // per message: one symbol's regime flips
  double move_follows_regime = 0.8;   // the rest of the moves go the other way
  double flow_bias = 0.15;            // P(new order is a buy) = 0.5 + flow_bias * regime
};

[[nodiscard]] std::vector<std::byte> make_synthetic_feed(const SyntheticFeedConfig& cfg);

}  // namespace hft::itch
