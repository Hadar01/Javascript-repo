# hft_lob

A C++20 market-data pipeline: it parses Nasdaq TotalView-ITCH 5.0, rebuilds a
limit order book, and runs a small ML model on order-book features in
microseconds. Every stage is benchmarked (median and p99).

> Status: stage 1 of 5 done: ITCH parser and full-market order book, with
> no heap allocation on the hot path (enforced by a test).
> See [LEARNING.md](LEARNING.md) for the design notes and trade-offs.

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
| 1 | ITCH 5.0 parser and limit order book | done |
| 2 | Lock-free SPSC ring buffer, two-thread pipeline | — |
| 3 | UDP multicast replay | — |
| 4 | Order-book features, Python training, C++ inference | — |
| 5 | End-to-end latency benchmarks and charts | — |

### Stage 1 design in brief

- **Parser** (`include/hft/itch/parser.hpp`)
  - `switch` on the message type; the handler is a template parameter, so `handler.on(msg)` is inlined into the parse loop.
  - Big-endian fields are read with `memcpy` + `bswap`: defined behaviour, and a single `movbe` with `-march=haswell`.
- **Order table** (`include/hft/book/order_table.hpp`)
  - Open addressing with linear probing, allocated once, at most 50% full.
  - Fibonacci hashing; backward-shift deletion (no tombstones).
- **Price levels** (`include/hft/book/order_book.hpp`)
  - One sorted `std::vector` per side, best price at the back.
  - Lookup is a linear scan from the top of the book.
- **Market book** (`include/hft/book/market_book.hpp`)
  - The ITCH handler: one order table for the whole market, books indexed by stock locate.
  - Feed anomalies are counted rather than thrown.

## Repository layout

```
include/hft/
  common/     types.hpp, mapped_file.hpp
  itch/       wire.hpp (big-endian I/O), messages.hpp, parser.hpp,
              encoder.hpp, synthetic.hpp
  book/       order_table.hpp, order_book.hpp, market_book.hpp
src/          code off the hot path: mmap wrapper, synthetic feed generator
apps/         itch_stats (replay a file through the book), itch_synth (make a feed)
tests/        GoogleTest, one executable per component; support/reference_book.hpp
bench/        Google Benchmark: clock cost, parser and book throughput
cmake/        Sanitizers, CompilerWarnings, Dependencies
scripts/      data download
```

The hot path is header-only so it can be inlined across components. Later
stages add the replay server and feed handler apps, and `python/`.

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

The 56 tests pass in all four presets, and with Clang 18. They include:

- a differential test of the order book against a `std::map` reference implementation
- a test that replaces global `operator new` to prove the trading path makes zero allocations
- sanitizer canaries that commit deliberate bugs and pass only if the sanitizer catches them

## Running it

```bash
# No download needed: a synthetic feed (structurally like ITCH, not real prices)
./build/release/apps/itch_synth /tmp/synth.itch --messages 2000000
./build/release/apps/itch_stats /tmp/synth.itch --symbol SYN3

# Real Nasdaq data (see "Market data" below)
./build/release/apps/itch_stats data/01302019.NASDAQ_ITCH50 --symbol AAPL
```

`itch_stats` prints:

- throughput
- message counts
- feed anomalies (all should be zero for a file that starts at the beginning of the day)
- peak live orders, which tells you what to pass to `--max-orders`
- level growth events (allocations after setup)
- the top 5 levels of the chosen symbol, and how often its book was locked or crossed (should be about zero, since Nasdaq matches crossing orders)

Its timing includes first-touch page faults on the input file, so use the
benchmarks for clean numbers.

## Benchmarks

```bash
taskset -c 2 ./build/release/bench/clock_bench
taskset -c 2 ./build/release/bench/itch_bench
```

For stable numbers, also set the CPU frequency governor to performance:
`sudo cpupower frequency-set -g performance`.

Results so far (cloud VM, Intel Xeon @ 2.1 GHz, 2 MB L2 per core, GCC 13,
`-O2`, pinned to one core, median of 5 runs):

| Clock read | Time per call |
|-----------|---------------|
| `std::chrono::steady_clock::now()` | 27.1 ns |
| `__rdtsc()` | 14.8 ns |
| `__rdtscp()` | 20.7 ns |

Mean time per message over a whole synthetic feed:

| Workload | Parse only | Parse + `MarketBook` | Parse + `std::map` reference book |
|---|---|---|---|
| small: 4k live orders (order table ≈ 400 KB, fits in L2) | 15.2 ns | 48.8 ns | 103.3 ns |
| large: 500k live orders (table ≈ 48 MB, doesn't fit in L2) | 15.0 ns | 150.0 ns | 338.9 ns |

The large case is memory-bound: random lookups in a 48 MB table on 4 KB
pages, so cache misses plus TLB misses. Parse-only cost is dominated by
streaming the feed from memory and by mispredicting the jump on message type
(≈8–9 ns per message when types arrive in random order; measured in
LEARNING.md). Per-message p50/p99 latencies and the latency chart arrive in
stage 5.

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
