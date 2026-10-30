// itch_stats: replay an ITCH 5.0 BinaryFILE through the parser and the order
// book, then report throughput, message counts, anomalies, and the book of
// one symbol.
//
//   itch_stats FILE [--symbol AAPL] [--max-orders N] [--levels N]
//
// On real Nasdaq data, a correct book has:
//   - zero unknown_order / duplicate_order / overfill / book_mismatch
//     (the file starts at the beginning of the day, so every order's Add is
//     in it)
//   - a best bid below the best ask almost always ("locked/crossed updates"
//     close to zero). Nasdaq matches crossing orders, so its own displayed
//     book shouldn't cross.
// If those numbers aren't (near) zero, something is wrong in our code.

#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <string>
#include <string_view>
#include <system_error>

#include "hft/book/market_book.hpp"
#include "hft/common/mapped_file.hpp"
#include "hft/itch/parser.hpp"

namespace {

using hft::Locate;
using hft::Side;
using hft::book::MarketBook;

// Forwards every message to the book, and watches one symbol for a locked
// or crossed book after each of its updates.
struct StatsHandler {
  MarketBook& book;
  std::string_view watch_symbol;
  Locate watch = 0;  // 0 = not resolved yet. Nasdaq never assigns locate 0 to a stock.
  std::uint64_t watched_updates = 0;
  std::uint64_t locked_or_crossed = 0;

  void on(const hft::itch::StockDirectory& m) {
    book.on(m);
    if (!watch_symbol.empty() && hft::itch::trim_symbol(m.stock) == watch_symbol) watch = m.hdr.locate;
  }

  // Every other message MarketBook handles. The requires clause keeps this
  // template from claiming types MarketBook can't take (e.g. SystemEvent),
  // so the parser skips those at compile time.
  template <typename M>
    requires hft::itch::Handles<MarketBook, M>
  void on(const M& m) {
    book.on(m);
    if (m.hdr.locate == watch && watch != 0) {
      ++watched_updates;
      const auto& b = book.book(watch);
      const auto bid = b.best(Side::Buy);
      const auto ask = b.best(Side::Sell);
      if (bid && ask && bid->price >= ask->price) ++locked_or_crossed;
    }
  }
};

bool parse_size(std::string_view s, std::size_t& out) {
  // from_chars: no exceptions, no locale, no allocation.
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

int usage() {
  std::fprintf(stderr, "usage: itch_stats FILE [--symbol SYM] [--max-orders N] [--levels N]\n");
  return 2;
}

std::string dollars(hft::Price p) {
  char buf[32];
  std::snprintf(buf, sizeof buf, "%u.%04u", p / 10'000, p % 10'000);
  return buf;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string path = argv[1];
  std::string_view symbol;
  hft::book::MarketBookConfig cfg{.max_orders = std::size_t{4} << 20, .levels_per_side = 64};

  for (int i = 2; i < argc; ++i) {
    const std::string_view flag = argv[i];
    if (i + 1 >= argc) return usage();
    const std::string_view value = argv[++i];
    if (flag == "--symbol") {
      symbol = value;
    } else if (flag == "--max-orders") {
      if (!parse_size(value, cfg.max_orders)) return usage();
    } else if (flag == "--levels") {
      if (!parse_size(value, cfg.levels_per_side)) return usage();
    } else {
      return usage();
    }
  }

  try {
    const hft::MappedFile file(path);
    MarketBook book(cfg);
    StatsHandler handler{.book = book, .watch_symbol = symbol};

    const auto t0 = std::chrono::steady_clock::now();
    const auto feed = hft::itch::parse_binary_file(file.bytes(), handler);
    const auto t1 = std::chrono::steady_clock::now();

    const double secs = std::chrono::duration<double>(t1 - t0).count();
    const auto& s = book.stats();
    std::printf("file            %s (%.1f MB)\n", path.c_str(), static_cast<double>(file.size()) / 1e6);
    std::printf("messages        %llu in %.3f s: %.1f ns/msg, %.1f M msg/s\n",
                static_cast<unsigned long long>(feed.messages), secs,
                secs * 1e9 / static_cast<double>(feed.messages),
                static_cast<double>(feed.messages) / secs / 1e6);
    std::printf("skipped types   %llu   malformed %llu   trailing bytes %zu\n",
                static_cast<unsigned long long>(feed.unknown_type),
                static_cast<unsigned long long>(feed.malformed), feed.trailing_bytes);
    std::printf("book msgs       add %llu  exec %llu  cancel %llu  delete %llu  replace %llu\n",
                static_cast<unsigned long long>(s.adds), static_cast<unsigned long long>(s.executions),
                static_cast<unsigned long long>(s.cancels), static_cast<unsigned long long>(s.deletes),
                static_cast<unsigned long long>(s.replaces));
    std::printf("live orders     %zu at end, %llu peak (table holds %zu)\n", book.live_orders(),
                static_cast<unsigned long long>(s.peak_orders), cfg.max_orders);
    std::printf("anomalies       unknown %llu  duplicate %llu  overfill %llu  locate %llu  "
                "table_full %llu  book_mismatch %llu\n",
                static_cast<unsigned long long>(s.unknown_order),
                static_cast<unsigned long long>(s.duplicate_order),
                static_cast<unsigned long long>(s.overfill),
                static_cast<unsigned long long>(s.locate_mismatch),
                static_cast<unsigned long long>(s.table_full),
                static_cast<unsigned long long>(s.book_mismatch));
    std::printf("level growths   %llu (allocations after setup)\n",
                static_cast<unsigned long long>(book.level_growth_events()));

    if (!symbol.empty()) {
      if (handler.watch == 0) {
        std::printf("\nsymbol %.*s not found in the stock directory\n", static_cast<int>(symbol.size()),
                    symbol.data());
        return 1;
      }
      const auto& b = book.book(handler.watch);
      std::printf("\n%.*s (locate %u): %llu updates, %llu left the book locked or crossed\n",
                  static_cast<int>(symbol.size()), symbol.data(), static_cast<unsigned>(handler.watch),
                  static_cast<unsigned long long>(handler.watched_updates),
                  static_cast<unsigned long long>(handler.locked_or_crossed));
      std::printf("%12s %8s %10s | %-10s %8s %12s\n", "bid qty", "orders", "bid", "ask", "orders", "ask qty");
      for (std::size_t d = 0; d < 5; ++d) {
        const auto bid = b.level(Side::Buy, d);
        const auto ask = b.level(Side::Sell, d);
        std::printf("%12s %8s %10s | %-10s %8s %12s\n",
                    bid ? std::to_string(bid->qty).c_str() : "",
                    bid ? std::to_string(bid->order_count).c_str() : "",
                    bid ? dollars(bid->price).c_str() : "",
                    ask ? dollars(ask->price).c_str() : "",
                    ask ? std::to_string(ask->order_count).c_str() : "",
                    ask ? std::to_string(ask->qty).c_str() : "");
      }
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "itch_stats: %s\n", e.what());
    return 1;
  }
  return 0;
}
