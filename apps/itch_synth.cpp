// itch_synth: write a synthetic ITCH 5.0 BinaryFILE (see hft/itch/synthetic.hpp).
//
//   itch_synth OUT [--messages N] [--symbols N] [--live N] [--seed N]
//
// Lets you run itch_stats, the benchmarks and (later) the replay server
// without downloading Nasdaq's sample files.

#include <charconv>
#include <cstdint>
#include <cstdio>
#include <string_view>

#include "hft/itch/synthetic.hpp"

namespace {

template <typename T>
bool parse_uint(std::string_view s, T& out) {
  const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
  return ec == std::errc{} && ptr == s.data() + s.size();
}

int usage() {
  std::fprintf(stderr, "usage: itch_synth OUT [--messages N] [--symbols N] [--live N] [--seed N]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();
  const char* out_path = argv[1];
  hft::itch::SyntheticFeedConfig cfg;

  for (int i = 2; i < argc; ++i) {
    const std::string_view flag = argv[i];
    if (i + 1 >= argc) return usage();
    const std::string_view value = argv[++i];
    bool ok = false;
    if (flag == "--messages") ok = parse_uint(value, cfg.messages);
    else if (flag == "--symbols") ok = parse_uint(value, cfg.symbols) && cfg.symbols > 0;
    else if (flag == "--live") ok = parse_uint(value, cfg.target_live_orders);
    else if (flag == "--seed") ok = parse_uint(value, cfg.seed);
    if (!ok) return usage();
  }

  const auto feed = hft::itch::make_synthetic_feed(cfg);

  std::FILE* f = std::fopen(out_path, "wb");
  if (f == nullptr) {
    std::perror(out_path);
    return 1;
  }
  const bool written = std::fwrite(feed.data(), 1, feed.size(), f) == feed.size();
  if (std::fclose(f) != 0 || !written) {
    std::perror(out_path);
    return 1;
  }
  std::printf("wrote %zu bytes (%llu order messages, %u symbols) to %s\n", feed.size(),
              static_cast<unsigned long long>(cfg.messages), static_cast<unsigned>(cfg.symbols), out_path);
  return 0;
}
