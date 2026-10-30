// Proves the hot path doesn't allocate: this executable replaces the global
// operator new and delete with versions that count calls, then runs a whole
// synthetic feed through the parser and MarketBook.
//
// Replacing operator new is legal C++: a program may define its own, and
// every new-expression in the program (including those inside the standard
// library) then uses it. That is why this test is a separate executable.
// The replacement would change allocation for every test linked into it.
//
// Every form is replaced: plain, array, aligned and nothrow, plus every
// matching delete. In a normal build the standard library's array and
// nothrow forms forward to the plain one, so replacing that would be enough.
// Sanitizer runtimes replace all the forms themselves, though. Under ASan, a
// form we skipped would bypass our counter (the test could pass when it
// shouldn't), and its memory would come back through our free(), which ASan
// reports as an alloc-dealloc mismatch. That's how we found out.

#include <gtest/gtest.h>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <new>
#include <span>
#include <utility>
#include <vector>

#include "hft/book/market_book.hpp"
#include "hft/itch/parser.hpp"
#include "hft/itch/synthetic.hpp"

namespace {

// Plain counter: this test is single-threaded.
std::size_t g_allocations = 0;

void* counted_alloc(std::size_t size, std::size_t align) noexcept {
  ++g_allocations;
  if (size == 0) size = 1;
  if (align <= alignof(std::max_align_t)) return std::malloc(size);
  // aligned_alloc requires the size to be a multiple of the alignment.
  return std::aligned_alloc(align, (size + align - 1) / align * align);
}

void* counted_alloc_or_throw(std::size_t size, std::size_t align) {
  if (void* p = counted_alloc(size, align)) return p;
  throw std::bad_alloc();
}

constexpr std::size_t kDefault = 0;
std::size_t al(std::align_val_t a) { return static_cast<std::size_t>(a); }

}  // namespace

// noinline: the standard forbids declaring replacements inline, and if GCC
// inlines them anyway it sees free() applied to a pointer from operator new
// and reports a false -Wmismatched-new-delete. It can't tell that our
// operator new got that pointer from malloc.
// clang-format off
[[gnu::noinline]] void* operator new  (std::size_t n)                     { return counted_alloc_or_throw(n, kDefault); }
[[gnu::noinline]] void* operator new[](std::size_t n)                     { return counted_alloc_or_throw(n, kDefault); }
[[gnu::noinline]] void* operator new  (std::size_t n, std::align_val_t a) { return counted_alloc_or_throw(n, al(a)); }
[[gnu::noinline]] void* operator new[](std::size_t n, std::align_val_t a) { return counted_alloc_or_throw(n, al(a)); }
[[gnu::noinline]] void* operator new  (std::size_t n, const std::nothrow_t&) noexcept { return counted_alloc(n, kDefault); }
[[gnu::noinline]] void* operator new[](std::size_t n, const std::nothrow_t&) noexcept { return counted_alloc(n, kDefault); }
[[gnu::noinline]] void* operator new  (std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept { return counted_alloc(n, al(a)); }
[[gnu::noinline]] void* operator new[](std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept { return counted_alloc(n, al(a)); }

[[gnu::noinline]] void operator delete  (void* p) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete  (void* p, std::size_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete  (void* p, std::align_val_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, std::align_val_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete  (void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete  (void* p, const std::nothrow_t&) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, const std::nothrow_t&) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete  (void* p, std::align_val_t, const std::nothrow_t&) noexcept { std::free(p); }
[[gnu::noinline]] void operator delete[](void* p, std::align_val_t, const std::nothrow_t&) noexcept { std::free(p); }
// clang-format on

namespace {

using hft::book::MarketBook;

// Counts allocations made while the object is alive.
class AllocationCounter {
 public:
  AllocationCounter() : start_(g_allocations) {}
  [[nodiscard]] std::size_t count() const { return g_allocations - start_; }

 private:
  std::size_t start_;
};

constexpr std::uint16_t kSymbols = 8;
constexpr std::uint64_t kOrderMessages = 300'000;

const std::vector<std::byte>& feed() {
  static const auto f = hft::itch::make_synthetic_feed(
      {.symbols = kSymbols, .messages = kOrderMessages, .target_live_orders = 4'000, .max_level_offset = 32, .seed = 3});
  return f;
}

// The feed has two phases, like a real trading day:
//   setup:   1 system event + 1 stock directory per symbol (pre-market).
//            Each directory message reserves that symbol's levels, which
//            allocates. That's intended: it happens before trading.
//   trading: the order messages, which must not allocate.
// Returns {setup bytes, trading bytes}.
std::pair<std::span<const std::byte>, std::span<const std::byte>> split_phases(std::span<const std::byte> buf) {
  std::size_t off = 0;
  for (std::size_t i = 0; i < 1u + kSymbols; ++i) {
    // load_be16 returns uint16_t, which would be promoted to int in `2 + ...`.
    off += 2 + std::size_t{hft::itch::load_be16(buf.data() + off)};
  }
  return {buf.first(off), buf.subspan(off)};
}

TEST(NoAllocation, CounterSeesAllocations) {
  // Check the checker: if the replacement weren't active, every other test
  // in this file would pass vacuously.
  const AllocationCounter c;
  // The compiler may delete a new/delete pair whose memory is never used,
  // even with a counting operator new. Storing the pointer in a volatile
  // variable makes it "used", so the allocation must happen.
  std::vector<int>* volatile v = new std::vector<int>(100);
  delete v;
  EXPECT_EQ(c.count(), 2u);  // the vector object and its buffer
}

TEST(NoAllocation, SetupAllocatesTwoReservesPerSymbol) {
  // Pins down what setup costs, so a change to it is noticed.
  const auto [setup, trading] = split_phases(feed());
  MarketBook book({.max_orders = 16'384, .levels_per_side = 64});
  std::size_t allocations = 0;
  {
    const AllocationCounter c;
    hft::itch::parse_binary_file(setup, book);
    allocations = c.count();
  }
  EXPECT_EQ(allocations, 2u * kSymbols);  // one bid vector + one ask vector each
}

TEST(NoAllocation, TradingAllocatesNothing) {
  const auto [setup, trading] = split_phases(feed());  // feed built before counting
  // levels_per_side = 64 > the feed's 32-tick depth, so no level vector
  // should ever need to grow.
  MarketBook book({.max_orders = 16'384, .levels_per_side = 64});
  hft::itch::parse_binary_file(setup, book);

  hft::itch::FeedStats stats;
  std::size_t allocations = 0;
  {
    const AllocationCounter c;
    stats = hft::itch::parse_binary_file(trading, book);
    allocations = c.count();
  }
  ASSERT_EQ(stats.messages, kOrderMessages);
  EXPECT_EQ(allocations, 0u);
  EXPECT_EQ(book.level_growth_events(), 0u);
}

TEST(NoAllocation, GrowthBeyondReserveIsTheOnlySourceOfAllocations) {
  // With only 2 levels reserved, books outgrow their reserve. Each growth
  // must show up both as one real allocation and as one growth event:
  // the counter in the book must be honest.
  const auto [setup, trading] = split_phases(feed());
  MarketBook book({.max_orders = 16'384, .levels_per_side = 2});
  hft::itch::parse_binary_file(setup, book);
  std::size_t allocations = 0;
  {
    const AllocationCounter c;
    hft::itch::parse_binary_file(trading, book);
    allocations = c.count();
  }
  EXPECT_GT(book.level_growth_events(), 0u);
  EXPECT_EQ(allocations, book.level_growth_events());
}

}  // namespace
