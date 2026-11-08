# hft_lob

A C++20 market-data pipeline: it parses Nasdaq TotalView-ITCH 5.0, rebuilds a
limit order book, and runs a small ML model on order-book features in
microseconds. Every stage is benchmarked (median and p99).

> Status: stages 0–3 of 5 done: ITCH parser, full-market order book, a
> two-thread pipeline joined by a lock-free SPSC ring buffer, and an
> exchange-style UDP multicast replay (MoldUDP64, A/B line arbitration). No
> heap allocation on the hot path (enforced by a test).
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
| 2 | Lock-free SPSC ring buffer, two-thread pipeline | done |
| 3 | UDP multicast replay | done |
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

### Stage 2 design in brief

- **Ring** (`include/hft/concurrency/spsc_ring.hpp`)
  - Bounded, lock-free, single-producer/single-consumer.
  - Release/acquire on the two indices.
  - The producer's and consumer's fields on separate 128-byte blocks, so the two cores don't fight over one cache line.
  - Each side caches the other side's index.
- **Feed handler** (`include/hft/feed/feed_handler.hpp`)
  - After each message that touches a subscribed symbol, it sends a 128-byte snapshot of the top 5 levels, but only if they changed.
  - When the ring is full it drops the update (the default) or waits.
  - Sequence numbers let the strategy detect drops as gaps.
- **Pipeline** (`include/hft/feed/pipeline.hpp`)
  - Two pinned, busy-polling threads, with a start handshake and a release/acquire shutdown followed by a final drain.

### Stage 3 design in brief

- **`replay_server`** packs ITCH messages into **MoldUDP64** packets (the format Nasdaq uses) and sends them over UDP multicast.
  - Each packet goes out at its messages' original time, scaled by `--speed`, and stays below the MTU.
  - It sends heartbeats when idle and an end-of-session packet at the end.
  - It can drop packets on purpose on line A and/or B, to test the receiver.
- **`feed_handler`**: a busy-polling network thread does `recv` → sequence check → ITCH → book → ring; the stage 2 strategy thread consumes the ring.
- **Sequence numbers** detect lost, duplicate and overlapping packets.
- **A/B arbitration** listens to two identical lines, merges them by sequence number, and waits briefly for the other line before declaring a gap.
- **Kernel buffer overflows** (`RcvbufErrors`) are reported separately, so losses inside our own process aren't blamed on the network.

## Repository layout

```
include/hft/
  common/      types.hpp, mapped_file.hpp, cpu.hpp (pause, pinning, TSC),
               latency_recorder.hpp
  itch/        wire.hpp (big-endian I/O), messages.hpp, parser.hpp,
               encoder.hpp, synthetic.hpp
  book/        order_table.hpp, order_book.hpp, market_book.hpp
  concurrency/ spsc_ring.hpp
  feed/        book_update.hpp, feed_handler.hpp, pipeline.hpp, measuring_consumer.hpp
  net/         moldudp64.hpp, sequence_tracker.hpp, udp_socket.hpp, mold_receiver.hpp
src/           code off the hot path: mmap wrapper, TSC calibration, synthetic feeds, sockets
apps/          itch_stats (replay a file through the book), itch_synth (make a feed),
               pipeline (feed thread + strategy thread over the ring),
               replay_server + feed_handler (the same over UDP multicast)
tests/         GoogleTest, one executable per component; support/reference_book.hpp
bench/         Google Benchmark: clock cost, parser and book throughput, SPSC ring, UDP round trip
cmake/        Sanitizers, CompilerWarnings, Dependencies
scripts/      data download
```

The hot path is header-only so it can be inlined across components. Stage 4
adds `python/` (training) and the C++ inference code.

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

The 95 tests pass in all four presets, and with Clang 18. They include:

- a differential test of the order book against a `std::map` reference implementation
- a test that replaces global `operator new` to prove the trading path makes zero allocations
- a two-thread stress test of the ring, run under ThreadSanitizer
- a deliberately broken (relaxed-ordering) ring that TSan must flag
- real UDP sockets on this machine: the whole feed sent and received, losses chosen by the test and counted exactly, A/B arbitration recovering every packet one line lost, and multicast (skipped where the machine can't loop multicast back)
- sanitizer canaries that commit deliberate bugs and pass only if the sanitizer catches them

## Running it

```bash
# No download needed: a synthetic feed (structurally like ITCH, not real prices)
./build/release/apps/itch_synth /tmp/synth.itch --messages 2000000
./build/release/apps/itch_stats /tmp/synth.itch --symbol SYN3

# Real Nasdaq data (see "Market data" below)
./build/release/apps/itch_stats data/01302019.NASDAQ_ITCH50 --symbol AAPL

# Two threads: feed on core 2, strategy on core 3, joined by the ring
./build/release/apps/pipeline /tmp/synth.itch --symbols SYN1,SYN3,SYN5
./build/release/apps/pipeline /tmp/synth.itch --symbols SYN1,SYN3,SYN5 --wait   # never drop
```

Over the network (two processes; start the receiver first, because UDP keeps nothing for later):

```bash
./build/release/apps/feed_handler --group 239.255.1.1:30001 --symbols SYN1,SYN3,SYN5 &
./build/release/apps/replay_server /tmp/synth.itch --group 239.255.1.1:30001 --speed 1

# A/B lines, each losing 1% of packets on purpose
./build/release/apps/feed_handler --group 239.255.1.1:30001 --group-b 239.255.1.2:30002 --symbols SYN3 &
./build/release/apps/replay_server /tmp/synth.itch --group 239.255.1.1:30001 --group-b 239.255.1.2:30002 \
    --drop-a 0.01 --drop-b 0.01
```

`--max-payload` defaults to 1372 bytes, because this container's network MTU is 1400. On a standard 1500-MTU network, use 1472.

`pipeline` reports:

- feed throughput
- updates published, unchanged and dropped
- sequence gaps seen by the strategy (they must equal the drops)
- the ring-hop latency distribution (p50 to max)
- whether the strategy's final view of each symbol matches the book

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
./build/release/bench/spsc_bench   # pins its own threads to cores 2 and 3
./build/release/bench/udp_bench    # likewise
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
LEARNING.md).

SPSC ring between two cores, ranges over 4 runs. Each variant changes one
thing from the real ring:

| Variant | Throughput, ns/item | Round trip p50 | Round trip p99 |
|---------|---------------------|----------------|----------------|
| `SpscRing` (padded, cached indices) | 52 – 84 | **537 – 611 ns** | **798 – 835 ns** |
| Unpadded | 83 – 128 | 660 – 826 ns | 911 – 1,117 ns |
| No index caching | 33 – 71 | 686 – 757 ns | 846 – 931 ns |
| `std::mutex` ring | 170 – 188 | 2,255 – 2,637 ns | 26,200 – 26,700 ns |

How to read it:

- **Latency is consistent across runs.** The real ring has the lowest round trip, and the mutex's p99 is 30× worse.
- **Streaming throughput on this cloud VM varies too much to rank the lock-free variants.** Index caching did not help it here (see LEARNING.md).

Full pipeline (2M messages, 3 symbols, 229,627 updates, 0 drops, 0 gaps):

- The feed runs at 91–101 ns per message, against 60 ns single-threaded.
- The ring hop (publish to receive) is **p50 339–369 ns, p90 470–537 ns.**
- p99 ranged from 1.5 µs to 2 ms. That's this VM's noise: a thread that does nothing but spin was paused for more than 1 ms several times in 2 seconds.

UDP between two pinned cores (round trip, 64-byte packets, median of 3 runs), against the ring:

| Path | Round trip p50 | Round trip p99 |
|------|----------------|----------------|
| SPSC ring, never enters the kernel | 0.54–0.61 µs | 0.80–0.84 µs |
| UDP loopback, busy-poll | 3.8–3.9 µs | 8.0–8.7 µs |
| UDP loopback, blocking (thread sleeps) | 28–29 µs | 62–68 µs |

Even busy-polling, the kernel's network stack costs about 6.5× the in-process ring, and sleeping costs another 7.5×. That's why trading systems use kernel-bypass networking.

End to end over multicast (2M messages, 327,539 packets):

- **Real time:** 0 gaps, and books identical to the file-based run.
- **With 1% simulated loss on each of two lines:** A/B arbitration lost 6–12 packets, against the ≈ 14–15 predicted (packets × 1% × 1%).
- **On one line with 1% loss:** 3,943 gaps, and the book went wrong (13,949 unknown-order anomalies).

Per-stage p50/p99 latencies and the latency chart arrive in stage 5.

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
