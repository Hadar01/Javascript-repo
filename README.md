# hft_lob

A C++20 market-data pipeline: it parses Nasdaq TotalView-ITCH 5.0, rebuilds a
limit order book, and runs a small ML model on order-book features in
microseconds. Every stage is benchmarked (median and p99).

> Status: stage 0 (build system, test and benchmark harness). Each later stage
> adds a component; see [LEARNING.md](LEARNING.md) for the design notes.

## Architecture (target)

```
 ITCH 5.0 file              replay_server                 feed_handler
 (BinaryFILE format) ──►  paces messages by  ──UDP──►  ┌─────────────────────────┐
                          their timestamps   multicast │ feed thread             │
                                                       │  recv → parse → book    │
                                                       │          │              │
                                                       │   SPSC ring buffer      │
                                                       │   (lock-free)           │
                                                       │          ▼              │
                                                       │ strategy thread         │
                                                       │  features → model       │
                                                       └─────────────────────────┘
```

| Stage | Component | State |
|-------|-----------|-------|
| 0 | CMake, presets, sanitizers, GoogleTest, Google Benchmark | done |
| 1 | ITCH 5.0 parser and limit order book | — |
| 2 | Lock-free SPSC ring buffer, two-thread pipeline | — |
| 3 | UDP multicast replay | — |
| 4 | Order-book features, Python training, C++ inference | — |
| 5 | End-to-end latency benchmarks and charts | — |

## Repository layout

```
CMakeLists.txt          top-level build: options, module includes, subdirectories
CMakePresets.json       debug / release / asan / tsan configurations
cmake/
  Sanitizers.cmake      HFT_SANITIZER=asan|tsan → global -fsanitize flags
  CompilerWarnings.cmake  hft::warnings, the warning flags for our own targets
  Dependencies.cmake    GoogleTest and Google Benchmark via FetchContent (pinned)
tests/                  GoogleTest, one executable per component
bench/                  Google Benchmark, one executable per component
scripts/                data download
data/                   market data (git-ignored)
```

Added in later stages: `include/hft/<component>/` (headers, where the hot
path lives so it can be inlined), `src/` (non-inline code), `apps/` (replay
server and feed handler executables) and `python/` (training and plots).

## Building

Requirements: Linux, GCC ≥ 12 or Clang ≥ 16, CMake ≥ 3.25, Ninja, git.

```bash
# Ubuntu 24.04
sudo apt install build-essential cmake ninja-build git
sudo apt install clang libclang-rt-18-dev   # optional: Clang and its sanitizer runtimes
```

Each preset configures, builds and tests in one command:

```bash
cmake --workflow --preset release   # -O2 -g, asserts off. Use for benchmarks.
cmake --workflow --preset debug     # -O0 -g, asserts on
cmake --workflow --preset asan      # AddressSanitizer + UndefinedBehaviorSanitizer
cmake --workflow --preset tsan      # ThreadSanitizer
```

Or step by step: `cmake --preset release`, `cmake --build --preset release`,
`ctest --preset release`. Build trees go to `build/<preset>/`.

To use Clang, set `CXX` on the first configure: `CXX=clang++ cmake --preset release --fresh`.

The `SanitizerCanary` tests deliberately commit a heap overflow, a signed
overflow and a data race, and pass only if the matching sanitizer catches it.
In a normal build they show as skipped.

## Benchmarks

```bash
./build/release/bench/clock_bench
```

For stable numbers, set the CPU frequency governor to performance and pin the
process to one core:
`sudo cpupower frequency-set -g performance && taskset -c 2 ./build/release/bench/clock_bench`.

Results so far (cloud VM, Intel Xeon @ 2.8 GHz, GCC 13, median of 5 runs):

| Benchmark | Time per call |
|-----------|---------------|
| `std::chrono::steady_clock::now()` | 21.5 ns |
| `__rdtsc()` | 11.0 ns |
| `__rdtscp()` | 14.7 ns |

The full latency table and chart arrive in stage 5.

## Market data

The primary dataset is Nasdaq TotalView-ITCH 5.0 sample days, from
<https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/>. The format specification is at
<https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf>.

```bash
scripts/fetch_itch_sample.sh                          # default day, fully decompressed
scripts/fetch_itch_sample.sh MMDDYYYY.NASDAQ_ITCH50.gz   # any file name from the listing
HEAD_MB=512 scripts/fetch_itch_sample.sh              # just the first 512 MB, for development
```

A full day is several GB compressed and much larger decompressed, so check
your free disk space first. Unit tests never read these files; they build
their ITCH messages in code.
