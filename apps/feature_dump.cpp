// feature_dump: write the training data for python/train.py.
//
//   feature_dump FILE --symbols SYM[,SYM...] --out PATH [--max-orders N]
//
// Runs the real two-thread pipeline (parser, book, ring, strategy thread) on
// an ITCH file. The strategy thread, instead of a model, records one row per
// book update of a subscribed symbol:
//   exch_ts u64 | mid2 i64 (bid + ask, so the mid is exact) | locate u16 | pad u16 | features f32[10] | pad u32
// = 64 bytes per row, written raw to PATH. Every padding byte is an explicit
// field: a file format must not depend on padding the compiler inserts. PATH.json holds the column names
// and the row layout, so Python reads both from here and never redefines them.
//
// The Wait policy is used: dropping updates would leave holes in the
// training data.

#include <cerrno>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <memory>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

#include "hft/common/mapped_file.hpp"
#include "hft/features/features.hpp"
#include "hft/feed/feed_handler.hpp"
#include "hft/feed/pipeline.hpp"

namespace {

using hft::features::FeatureBuilder;
using hft::features::FeatureVector;
using hft::features::kNumFeatures;

struct Row {
  std::uint64_t exch_ts;
  std::int64_t mid2;
  std::uint16_t locate;
  std::uint16_t pad;
  float f[kNumFeatures];
  std::uint32_t pad2;  // without it the compiler would add these 4 bytes silently (8-byte alignment)
};
static_assert(sizeof(Row) == 64, "python/hft_data.py assumes 64-byte rows");

struct Recorder {
  std::vector<Row> rows;  // reserved before the run; grows only if the guess was too small
  std::vector<std::pair<hft::Locate, FeatureBuilder>> builders;

  void operator()(const hft::feed::BookUpdate& u) {
    FeatureBuilder* fb = nullptr;
    for (auto& [loc, b] : builders) {
      if (loc == u.locate) fb = &b;
    }
    if (fb == nullptr) fb = &builders.emplace_back(u.locate, FeatureBuilder{}).second;
    FeatureVector x;
    if (!fb->update(u, x)) return;
    Row r{.exch_ts = u.exch_ts,
          .mid2 = static_cast<std::int64_t>(u.bids[0].price) + static_cast<std::int64_t>(u.asks[0].price),
          .locate = u.locate,
          .pad = 0,
          .f = {},
          .pad2 = 0};
    for (std::size_t i = 0; i < kNumFeatures; ++i) r.f[i] = x[i];
    rows.push_back(r);
  }
};

int usage() {
  std::fprintf(stderr, "usage: feature_dump FILE --symbols SYM[,SYM...] --out PATH [--max-orders N]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const std::string in_path = argv[1];
  std::string out_path;
  std::vector<std::string> symbols;
  hft::feed::FeedHandlerConfig cfg{.book = {.max_orders = std::size_t{4} << 20, .levels_per_side = 64},
                                   .on_full = hft::feed::OnFull::Wait};
  for (int i = 2; i < argc; ++i) {
    const std::string_view flag = argv[i];
    if (i + 1 >= argc) return usage();
    const std::string_view v = argv[++i];
    if (flag == "--out") {
      out_path = v;
    } else if (flag == "--symbols") {
      std::size_t start = 0;
      while (start <= v.size()) {
        const std::size_t comma = v.find(',', start);
        const auto end = comma == std::string_view::npos ? v.size() : comma;
        if (end > start) symbols.emplace_back(v.substr(start, end - start));
        start = end + 1;
      }
    } else if (flag == "--max-orders") {
      const auto [ptr, ec] = std::from_chars(v.data(), v.data() + v.size(), cfg.book.max_orders);
      if (ec != std::errc{} || ptr != v.data() + v.size()) return usage();
    } else {
      return usage();
    }
  }
  if (out_path.empty() || symbols.empty()) return usage();

  try {
    const hft::MappedFile file(in_path);
    auto ring = std::make_unique<hft::feed::UpdateRing>();
    auto handler = std::make_unique<hft::feed::FeedHandler>(cfg, *ring);
    for (const auto& s : symbols) handler->subscribe_ticker(s);
    Recorder rec;
    rec.rows.reserve(file.size() / 32);  // at most one row per message; ITCH messages average > 30 bytes
    rec.builders.reserve(symbols.size());
    const auto run = hft::feed::run_pipeline(file.bytes(), *handler, *ring, rec, {.feed_cpu = 2, .strategy_cpu = 3});

    std::FILE* out = std::fopen(out_path.c_str(), "wb");
    if (out == nullptr) throw std::system_error(errno, std::generic_category(), "open " + out_path);
    const bool ok = std::fwrite(rec.rows.data(), sizeof(Row), rec.rows.size(), out) == rec.rows.size();
    if (std::fclose(out) != 0 || !ok) throw std::system_error(errno, std::generic_category(), "write " + out_path);

    // Metadata for Python: column names and row layout come from here only.
    const std::string meta_path = out_path + ".json";
    std::FILE* meta = std::fopen(meta_path.c_str(), "w");
    if (meta == nullptr) throw std::system_error(errno, std::generic_category(), "open " + meta_path);
    std::fprintf(meta, "{\n  \"rows\": %zu,\n  \"row_bytes\": %zu,\n  \"num_features\": %zu,\n  \"tick\": %g,\n",
                 rec.rows.size(), sizeof(Row), kNumFeatures, hft::features::kTick);
    std::fprintf(meta, "  \"source\": \"%s\",\n  \"feature_names\": [", in_path.c_str());
    for (std::size_t i = 0; i < kNumFeatures; ++i) {
      std::fprintf(meta, "%s\"%s\"", i ? ", " : "", hft::features::kFeatureNames[i]);
    }
    std::fprintf(meta, "]\n}\n");
    std::fclose(meta);

    std::printf("%llu messages -> %zu rows (%zu symbols) -> %s (%.1f MB)\n",
                static_cast<unsigned long long>(run.feed.messages), rec.rows.size(), rec.builders.size(),
                out_path.c_str(), static_cast<double>(rec.rows.size() * sizeof(Row)) / 1e6);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "feature_dump: %s\n", e.what());
    return 1;
  }
  return 0;
}
