#include "hft/itch/synthetic.hpp"

#include <algorithm>
#include <array>
#include <string>

#include "hft/common/types.hpp"
#include "hft/itch/encoder.hpp"
#include "hft/itch/messages.hpp"

namespace hft::itch {

namespace {

// SplitMix64: a tiny, fast, well-mixed 64-bit RNG with a fully defined
// output sequence.
struct SplitMix64 {
  std::uint64_t state;
  std::uint64_t next() noexcept {
    std::uint64_t z = (state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  }
  // Uniform in [0, n). The modulo bias is negligible for the small n used here.
  std::uint64_t below(std::uint64_t n) noexcept { return next() % n; }
  std::uint32_t below32(std::uint32_t n) noexcept { return static_cast<std::uint32_t>(below(n)); }
};

struct LiveOrder {
  OrderRef ref;
  Locate locate;
  Side side;
  Price price;
  Qty shares;
};

constexpr Price kTick = 100;  // $0.01 in Price(4) units
constexpr Timestamp kOpen = 34'200'000'000'000;  // 09:30:00.000000000 in ns

class Generator {
 public:
  explicit Generator(const SyntheticFeedConfig& cfg) : cfg_(cfg), rng_{cfg.seed} {}

  std::vector<std::byte> run() {
    std::vector<std::byte> out;
    out.reserve(cfg_.messages * 32 + 64 * cfg_.symbols);
    live_.reserve(cfg_.target_live_orders * 2);

    encode_framed(SystemEvent{.hdr = header(0), .event_code = 'O'}, out);
    for (std::uint16_t s = 0; s < cfg_.symbols; ++s) {
      encode_framed(StockDirectory{.hdr = header(locate_of(s)), .stock = symbol_of(s)}, out);
    }
    for (std::uint64_t i = 0; i < cfg_.messages; ++i) step(out);
    return out;
  }

 private:
  static Locate locate_of(std::uint16_t s) { return static_cast<Locate>(s + 1); }  // 0 = no stock

  static std::array<char, 8> symbol_of(std::uint16_t s) {
    std::array<char, 8> sym;
    sym.fill(' ');
    const std::string name = "SYN" + std::to_string(s);
    std::copy_n(name.begin(), std::min(name.size(), sym.size()), sym.begin());
    return sym;
  }

  // Symbol s trades around $(100 + 10 * s).
  static Price mid_of(Locate locate) { return static_cast<Price>((100 + 10 * (locate - 1)) * 10'000); }

  Header header(Locate locate) {
    now_ += 1 + rng_.below(2'000);  // 1 ns to 2 us between messages
    return Header{.locate = locate, .tracking = 0, .timestamp = now_};
  }

  // Distance from mid in ticks. The min of two uniforms is skewed toward
  // small values, so most orders sit near the top of the book.
  Price draw_price(Locate locate, Side side) {
    const std::uint32_t offset = 1 + std::min(rng_.below32(cfg_.max_level_offset), rng_.below32(cfg_.max_level_offset));
    return side == Side::Buy ? mid_of(locate) - offset * kTick : mid_of(locate) + offset * kTick;
  }

  Qty draw_shares() { return 100 * (1 + rng_.below32(10)); }

  void step(std::vector<std::byte>& out) {
    // Below the target, adds win more often; above it, removals do. That
    // keeps the live order count around the target.
    const std::uint64_t add_pct = live_.size() < cfg_.target_live_orders ? 60 : 40;
    if (live_.empty() || rng_.below(100) < add_pct) {
      add(out);
      return;
    }
    const std::size_t idx = static_cast<std::size_t>(rng_.below(live_.size()));
    const std::uint64_t r = rng_.below(100);
    if (r < 70) {
      remove(out, idx);
    } else if (r < 85) {
      replace(out, idx);
    } else if (r < 93) {
      cancel(out, idx);
    } else {
      execute(out, idx);
    }
  }

  void add(std::vector<std::byte>& out) {
    const Locate locate = locate_of(static_cast<std::uint16_t>(rng_.below(cfg_.symbols)));
    const Side side = rng_.below(2) == 0 ? Side::Buy : Side::Sell;
    const LiveOrder o{.ref = next_ref_++, .locate = locate, .side = side,
                      .price = draw_price(locate, side), .shares = draw_shares()};
    encode_framed(AddOrder{.hdr = header(locate), .order_ref = o.ref, .side = o.side,
                           .shares = o.shares, .price = o.price},
                  out);
    live_.push_back(o);
  }

  // Swap with the last element and pop: O(1) removal from an unordered vector.
  void drop(std::size_t idx) {
    live_[idx] = live_.back();
    live_.pop_back();
  }

  void remove(std::vector<std::byte>& out, std::size_t idx) {
    const LiveOrder& o = live_[idx];
    encode_framed(OrderDelete{.hdr = header(o.locate), .order_ref = o.ref}, out);
    drop(idx);
  }

  void replace(std::vector<std::byte>& out, std::size_t idx) {
    LiveOrder& o = live_[idx];
    const OrderRef new_ref = next_ref_++;
    const Price price = draw_price(o.locate, o.side);
    const Qty shares = draw_shares();
    encode_framed(OrderReplace{.hdr = header(o.locate), .original_ref = o.ref, .new_ref = new_ref,
                               .shares = shares, .price = price},
                  out);
    o.ref = new_ref;
    o.price = price;
    o.shares = shares;
  }

  void cancel(std::vector<std::byte>& out, std::size_t idx) {
    LiveOrder& o = live_[idx];
    if (o.shares < 2) {
      remove(out, idx);
      return;
    }
    const Qty qty = 1 + rng_.below32(o.shares - 1);  // partial: leaves at least 1
    encode_framed(OrderCancel{.hdr = header(o.locate), .order_ref = o.ref, .cancelled_shares = qty}, out);
    o.shares -= qty;
  }

  void execute(std::vector<std::byte>& out, std::size_t idx) {
    LiveOrder& o = live_[idx];
    const Qty qty = 1 + rng_.below32(o.shares);  // may fill the whole order
    if (rng_.below(10) == 0) {
      encode_framed(OrderExecutedWithPrice{.hdr = header(o.locate), .order_ref = o.ref,
                                           .executed_shares = qty, .match_number = next_match_++,
                                           .printable = 'Y', .execution_price = o.price},
                    out);
    } else {
      encode_framed(OrderExecuted{.hdr = header(o.locate), .order_ref = o.ref,
                                  .executed_shares = qty, .match_number = next_match_++},
                    out);
    }
    o.shares -= qty;
    if (o.shares == 0) drop(idx);
  }

  SyntheticFeedConfig cfg_;
  SplitMix64 rng_;
  Timestamp now_ = kOpen;
  OrderRef next_ref_ = 1;
  std::uint64_t next_match_ = 1;
  std::vector<LiveOrder> live_;
};

}  // namespace

std::vector<std::byte> make_synthetic_feed(const SyntheticFeedConfig& cfg) { return Generator(cfg).run(); }

}  // namespace hft::itch
