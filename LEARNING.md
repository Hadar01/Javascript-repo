# Learning notes

Revision notes for each stage: the concepts, the decisions, and the
trade-offs behind them. Written to be re-read before an interview.

---

## Stage 0: build system, tests, benchmarks, data

### Modern CMake in one paragraph

Everything is a **target** (an executable, a library, or an `INTERFACE`
library that compiles nothing). Targets carry **usage requirements**:
include paths, compile flags, definitions, and libraries to link. A target
passes these on to whatever links it, depending on the keyword used:

| Keyword | Applies to the target itself | Passed on to whatever links it |
|---------|------------------------------|--------------------------------|
| `PRIVATE` | yes | no |
| `INTERFACE` | no | yes |
| `PUBLIC` | yes | yes |

The old style (`include_directories()`, `CMAKE_CXX_FLAGS += ...`) sets flags
for everything in the directory, and a large project ends up with flags
nobody can trace. Per-target settings scale.

- **`hft::warnings` is an INTERFACE library.** Linking it adds our warning
  flags to that target only, so GoogleTest and Google Benchmark never see
  them.
- **The `::` in `hft::warnings` is a safety feature.** CMake knows a name
  containing `::` must be a target. A typo is a configure error, not a silent
  `-lhft_warnigns` at link time.
- **Sanitizer flags are global on purpose.** It's the one place where we
  *want* them on every line of code we compile (see below).

### Dependencies: FetchContent, pinned tags

| Option | Why not (for this project) |
|--------|---------------------------|
| Distro packages (`apt install libgtest-dev`) | Version varies by machine; not built with our sanitizer flags |
| git submodules | Fine, but people forget `--recursive`; still need the CMake glue |
| Copying the source into the repo | Bloats the repository |
| vcpkg / Conan | A whole package-manager toolchain for two libraries |
| **FetchContent + `GIT_TAG vX.Y.Z`** | Reproducible, built with our flags, zero setup |

The `SYSTEM` keyword (CMake 3.25+) marks their headers as system headers, so
`-Wconversion` etc. don't fire inside `gtest.h`.

### Build types and compiler flags

| Preset | Build type | Flags | Asserts | Use for |
|--------|-----------|-------|---------|---------|
| `debug` | Debug | `-g` (no `-O` means `-O0`) | on | stepping through in gdb |
| `release` | RelWithDebInfo | `-O2 -g -DNDEBUG` | off | **benchmarks**, profiling |
| `asan` / `tsan` | Debug | `-O1 -g` + sanitizer | on | correctness |

- **`-g` doesn't make code slower.** GCC and Clang are designed so `-g` does
  not change the generated code. Debug info goes into separate `.debug_*`
  sections that are never loaded into memory at run time. You want it in
  release builds so `perf` can show function names and source lines.
- **`-O2` vs `-O3`.** `-O3` inlines, unrolls and vectorises more
  aggressively. That can be faster, or slower because the bigger code no
  longer fits the instruction cache. Never assume; benchmark both.
- **`-march=native`** (option `HFT_MARCH_NATIVE`) lets the compiler use every
  instruction your CPU has (AVX2, AVX-512, BMI2) and tune for it. The binary
  may die with `SIGILL` on an older CPU. In production you build for the
  exact server model (e.g. `-march=icelake-server`).
- **`NDEBUG` removes `assert`s entirely.** `assert(book.apply(msg))` is a
  bug: in release the call itself disappears. Never put side effects in an
  assert.
- **`CMAKE_CXX_EXTENSIONS OFF`** gives `-std=c++20` rather than
  `-std=gnu++20`, so GNU-only extensions don't creep in.
- **Default build type.** An empty `CMAKE_BUILD_TYPE` means no optimisation
  at all. The top-level CMakeLists defaults it to RelWithDebInfo so nobody
  benchmarks an `-O0` build by accident.

### Warnings we enable, and why each matters here

- `-Wconversion` / `-Wsign-conversion`: ITCH has 48-bit timestamps, 32-bit
  prices and 64-bit order IDs. Silently storing one in a narrower type is the
  classic feed-handler bug, and these flags turn it into a compile error.
- `-Wshadow`: a local `price` hiding a member `price` is an easy, silent bug.
- `-Wold-style-cast`: `(uint32_t)x` can mean `static_cast`, `const_cast` or
  `reinterpret_cast`. The named casts say which one you meant.
- `-Wdouble-promotion`: on the inference path a stray `0.5` (a double)
  turns float maths into double maths.
- `-Werror` is on in the presets, off by default. You want it while
  developing, but a newer compiler with new warnings shouldn't stop a
  stranger from building the code.

### Sanitizers

| Sanitizer | Catches | Typical slowdown |
|-----------|---------|------------------|
| ASan (`address`) | out-of-bounds (heap, stack, globals), use-after-free, double free, leaks | ~2x |
| UBSan (`undefined`) | signed overflow, misaligned loads, bad shifts, null dereference, object-size overflow | small |
| TSan (`thread`) | data races, lock-order inversions (deadlock risk) | 5–15x, 5–10x memory |

- **How they work.** The compiler inserts a check before memory accesses,
  and the runtime keeps "shadow memory" describing what each address may do.
  For TSan, the shadow records which thread accessed each address, and under
  which "happens-before" ordering.
- **ASan and TSan can't be combined.** Each reserves its own fixed shadow
  layout in the address space, and the two collide. Hence two builds.
- **Instrument everything, especially for TSan.** TSan can only see
  synchronisation in code it instrumented. Uninstrumented code that uses
  atomics or locks causes false race reports. That's why the sanitizer flags
  are global and the dependencies are built from source.
- **`-fno-sanitize-recover=all`.** By default UBSan prints a report and
  *continues*, so the test passes and nobody reads the log. With this flag
  every report is fatal.
- **Canary tests.** `tests/sanitizer_canary_test.cpp` commits one bug per
  sanitizer inside `EXPECT_DEATH`. A sanitizer build where the flags never
  reached the compiler would otherwise look "clean". You need to test your
  safety net.
- **The sanitizers overlap.** The first version of the ASan canary was
  caught by UBSan's object-size check before ASan saw it, because the compiler
  could see the pointer came from `new int[4]`. Fix: make the pointer
  `volatile` so the allocation size is invisible to the compiler.
- **MemorySanitizer** (uninitialised reads, Clang only) needs *everything*
  instrumented, including the C++ standard library. Not worth it here.
- **Clang's sanitizers need `libclang-rt-<ver>-dev`.** On Ubuntu, without
  it, linking fails with `cannot find libclang_rt.asan...`.
- **TSan's "unexpected memory mapping" crash.** Some kernels randomise the
  address space more than older TSan runtimes expect. Fix:
  `sudo sysctl vm.mmap_rnd_bits=28`.

### Benchmarking basics

- **The compiler deletes work whose result is unused.** Measured in this
  repo: summing 1024 integers without using the result reported
  **0.000 ns per iteration over 10¹² iterations**. With
  `benchmark::DoNotOptimize(result)` it was **456 ns**.
  - `DoNotOptimize(x)` tells the compiler `x` is read by something it can't
    see.
  - `benchmark::ClobberMemory()` tells it all memory may have been read or
    written.
- **Measure the ruler first** (`bench/clock_bench.cpp`). Median per call on
  the cloud VM: `steady_clock::now()` 21.5 ns, `__rdtsc()` 11.0 ns,
  `__rdtscp()` 14.7 ns. A 30 ns stage timed with a 21 ns clock is mostly
  clock.
- **`steady_clock`** → `clock_gettime(CLOCK_MONOTONIC)` → the vDSO, which
  runs in user space with no system call. That only holds if
  `/sys/devices/system/clocksource/clocksource0/current_clocksource` is `tsc`.
  With `hpet` or `acpi_pm` it falls back to a real system call, which is far
  slower.
- **RDTSC** reads the CPU's time-stamp counter.
  - The CPU flags `constant_tsc` (fixed rate, unaffected by frequency
    scaling) and `nonstop_tsc` (keeps counting in sleep states), both in
    `/proc/cpuinfo`, make it usable as a clock.
  - It returns ticks, so you calibrate ticks-per-ns once at startup.
  - It isn't serialising: the CPU may execute it before earlier instructions
    finish.
- **RDTSCP** waits for earlier instructions to finish before reading. Later
  instructions can still start early, so the usual pattern is
  `lfence; rdtsc` to start the timer and `rdtscp; lfence` to stop it.
  Stage 5 covers this.
- **Noise sources.**
  - CPU frequency scaling: set the governor to `performance`.
  - The scheduler moving the thread between cores: pin it with `taskset`.
  - Other processes on the same core: in production, `isolcpus` reserves
    whole cores.
  - Turbo boost and hyper-threading siblings.
  - Report the median *and* the tail (p99); the mean hides the outliers you
    care about.

### Market data: ITCH 5.0 vs LOBSTER

**Decision: ITCH 5.0.**

- It's the real binary wire format exchanges send, which is what an HFT
  firm's feed handlers parse.
- It covers the whole market, timestamps are in nanoseconds, and it has a
  real Order Replace message.

LOBSTER is CSV, derived from ITCH, one symbol per file, with no replace
message type: easier, but it teaches less. The cost of ITCH is size (a full
day is many GB). The workaround is `HEAD_MB=512` for development, and later
reading the file through `mmap` instead of loading it.

**File framing** (the `emi.nasdaq.com` sample files): `[2-byte big-endian
length][message]` repeated. Every message starts with
`type(1) stock_locate(2) tracking_number(2) timestamp(6)`. The timestamp is
nanoseconds since midnight, a 48-bit big-endian integer. Prices are 4-byte
integers with 4 implied decimal places (`1234500` = $123.45). Keep prices as
integers; never use floating point for prices in the book.

| Type | Message | Size | Book effect |
|------|---------|------|-------------|
| `A` | Add Order (no MPID) | 36 | new resting order |
| `F` | Add Order with MPID | 40 | new resting order |
| `E` | Order Executed | 31 | reduce shares |
| `C` | Order Executed with Price | 36 | reduce shares |
| `X` | Order Cancel | 23 | reduce shares |
| `D` | Order Delete | 19 | remove order |
| `U` | Order Replace | 35 | remove old ID, add new ID with new price and shares, same side |
| `R` | Stock Directory | 39 | maps stock_locate → symbol |
| `S` | System Event | 12 | start/end of day markers |

ITCH is big-endian and x86 is little-endian, so every multi-byte field needs
a byte swap: one `bswap` instruction, via `std::byteswap` (C++23) or
`__builtin_bswap32/64`. Stage 1 covers how to read those fields without
undefined behaviour.

### Common mistakes from this stage

1. Benchmarking a Debug build (or one with no build type at all).
2. A benchmark loop the compiler optimised away (fix with `DoNotOptimize`).
3. Assuming the sanitizer is on. Prove it with a canary.
4. UBSan reports that don't fail the test (fix with
   `-fno-sanitize-recover=all`).
5. TSan with uninstrumented libraries: false positives.
6. Applying `-Werror` to third-party code.
7. Side effects inside `assert`.
8. `-march=native` binaries copied to a different CPU: `SIGILL`.

### Interview questions (stage 0)

1. A benchmark reports your function at 0.3 ns per call. What is probably
   happening, and how do you fix it?
2. Why do the benchmarks use `-O2 -g -DNDEBUG`? Does `-g` slow the program
   down? What happens to `assert(book.apply(msg))` in that build?
3. Why are the warning flags applied only to our targets, but the sanitizer
   flags to everything, including GoogleTest? What goes wrong with TSan if a
   library isn't instrumented?
4. Why can't ASan and TSan run in the same binary? Why do we have canary
   tests, and what did the first ASan canary teach us?
5. You need to time a function that takes about 40 ns, using `rdtsc`. List
   the problems you face and how you'd deal with each.

#### Model answers (stage 0)

**1. 0.3 ns per call.**
- That's under one clock cycle, so no real work is being measured.
- The compiler removed it, in one of three ways:
  - the result is unused, so the call is dead code
  - the inputs are compile-time constants, so the result was computed while compiling
  - the call doesn't depend on the loop, so it was moved out of the loop
- Fix:
  - `benchmark::DoNotOptimize` on the result, and on the inputs if they're constants
  - `benchmark::ClobberMemory()` if the work is a write to memory
  - read inputs from run-time data
  - check the assembly

**2. `-O2 -g -DNDEBUG` for benchmarks.**
- It's what you ship:
  - `-O2` is production optimisation
  - `NDEBUG` removes asserts, as in production
  - `-g` costs nothing at run time, because it doesn't change the generated code and the debug sections are never loaded; `perf` needs it to show function names
- `assert(book.apply(msg))` disappears entirely under `NDEBUG`, so `apply` is never called and the book never updates.
- Write `const bool ok = book.apply(msg); assert(ok);` instead.

**3. Warnings only on our code, sanitizers on everything.**
- Warnings: we can't fix third-party code, and `-Werror` on it breaks the build whenever a new compiler adds a warning.
- Sanitizers work only on code they instrumented:
  - TSan learns about synchronisation from instrumented atomic and lock operations.
  - A library built without it that synchronises internally (say, a lock-free queue) looks unsynchronised to TSan.
  - That gives false race reports, and real races inside that library go unseen.
  - ASan still intercepts `malloc` everywhere, but can't check the loads and stores in uninstrumented code.

**4. Why ASan + TSan can't be combined, and why canaries.**
- **Can't combine:** each one reserves fixed address-space regions for its shadow memory, in incompatible layouts, and each replaces `malloc` and friends.
- **Why canaries:**
  - The flags can silently fail to reach the compiler: wrong preset, or the include order in CMake.
  - Reports can be non-fatal, so the test still passes.
  - A canary proves the sanitizer is on and its reports fail the test.
- **What the first ASan canary taught us:** UBSan's object-size check caught the overflow first.
  - The sanitizers overlap.
  - A death test must check *which* error occurred (the regex), not just that the process died.
  - The bug must be hidden from the compiler (with `volatile`) so the intended tool sees it.

**5. Timing 40 ns with `rdtsc`.**
- **The ruler is too coarse.** One read costs 11–15 ns (measured), comparable to the 40 ns. Subtract the measured empty-timer cost, or time a batch of N calls and divide.
- **Out-of-order execution.** `rdtsc` can run before earlier instructions finish, or after later ones start. Use `lfence; rdtsc` to start and `rdtscp; lfence` to stop.
- **Ticks, not nanoseconds.** Calibrate ticks-per-ns against `steady_clock` at startup. That needs the `constant_tsc` and `nonstop_tsc` CPU flags.
- **Core migration.** Pin the thread. `rdtscp` also returns the core ID, so you can detect a move.
- **The compiler can move code across the intrinsic.** Put a compiler barrier around it (`std::atomic_signal_fence` or `asm volatile("" ::: "memory")`).
- **Noise.** Frequency scaling, interrupts, cold caches. Warm up, take many samples, and report the median and p99, not a single number.

---

## Stage 1: ITCH parser and limit order book

### The pipeline

```
file ──mmap──► span<const byte> ──parse_binary_file──► parse_message ──handler.on(msg)──► MarketBook
                 (MappedFile)      [len][msg][len][msg]   switch on type            ├─ OrderTable  (ref → order)
                                                          decode fields             └─ OrderBook[locate] (price levels)
```

| File | Role | Hot path? |
|------|------|-----------|
| `itch/wire.hpp` | big-endian loads/stores at any offset | yes |
| `itch/messages.hpp` | decoded message structs | yes |
| `itch/parser.hpp` | type dispatch + BinaryFILE framing | yes |
| `book/order_table.hpp` | live orders, open-addressing hash table | yes |
| `book/order_book.hpp` | one symbol's price levels | yes |
| `book/market_book.hpp` | ITCH handler tying the two together | yes |
| `common/mapped_file.*` | RAII mmap of the input file | setup |
| `itch/encoder.hpp`, `itch/synthetic.*` | building test and benchmark feeds | no |

### Reading big-endian fields without undefined behaviour

`*reinterpret_cast<const uint32_t*>(p)` breaks two rules:

- **Alignment:** `p` may not be a multiple of 4.
- **Strict aliasing:** the bytes are `std::byte` objects, and reading them through a `uint32_t` lvalue is UB. (The rule only lets you go the other way: read any object as bytes.)

The compiler may assume neither violation happens and optimise accordingly. Code like this usually "works" until a new compiler version or flag breaks it.

`std::memcpy(&v, p, 4)` is defined behaviour and costs nothing. Checked in the assembly:

```
mov   eax, DWORD PTR 32[rdi]   ; one unaligned load (fine on x86)
bswap eax                      ; one byte swap
```

With `-march=haswell` that becomes a single `movbe` (load and byte-swap in one instruction). The 48-bit timestamp is a 2-byte load plus a 4-byte load. Never read 8 bytes for it: the extra 2 belong to the next field, and they may lie past the end of the buffer.

### Decoded structs vs alternatives

| Option | Pros | Cons |
|--------|------|------|
| `#pragma pack` struct overlaid on the bytes | "zero copy" | still needs byte swaps; aliasing UB; references to packed members are misaligned |
| Lazy view: pointer + accessor per field | decodes only what's read | more code; every access re-decodes |
| **Decoded host-order struct (chosen)** | plain aligned struct, `operator==`, easy to test | decodes fields up front |

The "decodes up front" cost disappears once the parser and handler are inlined together. The compiler drops the loads for fields nobody reads. Observed: with a handler that reads only the header, GCC merged all nine `case`s into one shared header-decode block.

### Static dispatch: the handler as a template parameter

`parse_message<Handler>` calls `handler.on(msg)`. Because the type is known at compile time, the call can be inlined into the parse loop and optimised with it. The alternatives cost more:

| Option | Cost |
|--------|------|
| Virtual function | Indirect call per message; can't be inlined |
| `std::function` | Indirect call, plus possible heap allocation for captures |
| `std::variant` + `std::visit` | Builds a variant per message; another jump table |
| **Template handler (chosen)** | None; the compiler sees through it |

A handler only implements `on()` for the types it wants:

- The concept `Handles<H, M>` is a `requires` expression that asks "is `h.on(m)` valid?".
- `if constexpr (Handles<Handler, M>)` removes the decode and the call at compile time for any other type.

### Measured: where parse time goes (in-cache feed, 2.1 GHz Xeon)

| Experiment | ns/msg | What it shows |
|------------|--------|---------------|
| Framing only (follow length prefixes) | 2.6 | Floor: each message's address depends on loading the previous one's length (a dependent load chain, ≈5–6 cycles) |
| Framing only, 60 MB feed (L3, not L2) | 9.1–9.6 | The same chain stops the CPU from running ahead and issuing later loads early, so misses are paid one at a time |
| Full parse, types sorted (predictable) | 3.1–3.3 | Decode work is cheap |
| Full parse, types shuffled | 11.2–12.6 | **≈8–9 ns = mispredicted indirect jump on the type `switch`** |
| Full parse before `always_inline` | 12.8 | `parse_message` was a real call per message; the handler's sum lived in memory |

Lessons:

- **The first hypothesis was right, but the first experiment couldn't show it.** It mixed in two other effects: a non-inlined call, and a feed too big for L2. Change one variable at a time.
- **`inline` and templates only *allow* inlining.** GCC refused for a nine-case function. Check with `nm -C binary | grep parse_message`: if the symbol exists, it wasn't inlined everywhere. We force it with `[[gnu::always_inline]]` only because there's one hot caller and the gain was measured.
- **Random message types cost one mispredict per message.** That's the price of the data, not of the code. `[[unlikely]]` on the error checks keeps the error code out of the hot path, but can't fix an unpredictable jump.

### Framing robustness

- **Overflow-safe bounds checks.** `size - off >= 2`, not `off + 2 <= size`: the subtraction can't overflow, because `off <= size` always holds.
- **Truncated last message.** Not parsed; reported in `trailing_bytes`. A `HEAD_MB` slice of a file always ends this way.
- **Zero-length message.** Counted as malformed and skipped. It can't loop forever, because `off` still advances by 2.
- **Longer than the spec.** Accepted, and the extra bytes are ignored. That's forward-compatible with a spec revision that adds a field.
- **Bad side byte.** Rejected before the cast to `Side`. An enum holding a value the code thinks can't exist is a time bomb.

### OrderTable: open addressing done right

- **Why not `std::unordered_map`.**
  - It allocates a node on every insert and frees it on every erase.
  - Each lookup reads a bucket array and then chases a pointer, usually two cache misses.
- **One flat array of 24-byte entries**, allocated and written once at construction. Writing it touches every page, so the kernel maps them all at startup, not as page faults mid-session.
- **Power-of-two size**, so `& mask` wraps an index instead of a slow `%`.
- **Load ≤ 50%.** The slot count is the next power of two at or above `2 × max_orders`. Linear probing gets slow past about 70% full (long clusters).
- **Fibonacci hashing:** `(key * 0x9E3779B97F4A7C15) >> (64 - bits)`. Multiplication pushes low-bit differences *up*, so the top bits depend on every key bit. Keep the top bits; the bottom bits of the product depend only on the bottom bits of the key.
- **Backward-shift deletion instead of tombstones.**
  - Tombstones accumulate over a day of ~100M deletes, until lookups scan long runs of dead slots.
  - Backward shift moves later entries of the cluster back into the hole.
  - An entry at `j` with home `h` may move to the hole `i` only if `i` lies on its probe path: `dist(h→j) >= dist(i→j)`. Otherwise it would sit before its home, where `find` never looks.
- **Pointer invalidation.** `erase` can move other entries, so any `OrderEntry*` is invalid after an erase. `on(OrderReplace)` copies the side and locate out *before* removing the old order.
- **Full table.** Insert fails and `table_full` counts it. The table never grows (no rehash pause mid-session); size it from the peak live-order count, which `itch_stats` reports.

### OrderBook: sorted vector, best price at the back

- **Most activity is near the top of the book.** With the best price at the back, updates touch the end of the vector, and insert or erase shifts only a few 16-byte `Level`s.
- **The search is a linear scan from the back.** It's short for near-top prices, its branch is predictable, and it reads memory sequentially. Binary search would jump around, and its comparisons are close to random, so it mispredicts.
- **`if constexpr` on a `Side` template parameter** gives each side its own comparison at compile time, with no side branch inside the loop.
- **Rejected alternatives:**
  - `std::map`: a node allocation per new level, and pointer chasing per lookup.
  - A price-indexed array: O(1) by price, but it needs a bounded, re-centred price range per symbol, and finding the next best level after one empties means scanning.
- **Levels aggregate shares and order count, not a queue of orders.** That's all the features need (spread, imbalance, microprice). The trade-off is no queue-position information. That would need a per-level linked list of orders, which we can add if a strategy needs it.
- **Queries return `std::optional<Level>` by value.** A pointer or span into the vector would silently point at a *different* level after the next insert shifts the elements. That's a wrong-data bug with no crash, which even ASan can't see unless the vector reallocated.

### MarketBook

- **One `OrderTable` for the whole market.** Order references are unique across all symbols.
- **`std::vector<OrderBook>` with 65,536 entries, indexed by stock locate.** Lookup is an array index, not a hash.
- **Level reserves happen on Stock Directory (`R`) messages**, which arrive pre-market. Trading messages never allocate unless a symbol outgrows its reserve, and that is counted in `level_growth_events`.
- **Bad input never crashes and never corrupts the book silently.**
  - Unknown order, duplicate reference, overfill, wrong locate, full table, or a level missing for a live order: each is counted in `BookStats`.
  - Each is handled conservatively: ignore the message, or clamp the share count.
  - No exceptions on the hot path; errors are counters you can alert on.

### How "no heap allocation on the hot path" is guaranteed

1. **Preallocate at setup.** The order table, the vector of books, and the per-symbol level reserves (at stock directory time).
2. **Never grow silently.** The table refuses inserts when full (`table_full`). Level growth is counted (`level_growth_events`).
3. **Prove it with a test.** `no_alloc_test` replaces global `operator new`/`delete` with counting versions, runs the trading phase of a feed, and requires **0 allocations**. It also checks the checker: a known allocation is counted, and with a tiny reserve, allocations == growth events exactly.

The first version of the test was wrong in two ways:

- **It counted setup as trading.** It reported 16 allocations: 8 symbols × 2 sides, from the reserves in the stock directory messages. The fix splits the feed into a setup phase and a trading phase, as on a real trading day.
- **It replaced too few forms of `operator new`.** Normally the array and `nothrow` forms forward to the plain one, but ASan's runtime replaces them all itself. Under ASan, GoogleTest's `stable_sort` buffer (a `nothrow` new) bypassed the counter, and ASan reported "alloc-dealloc-mismatch (operator new vs free)". The fix replaces every form: plain, array, aligned, `nothrow`, and every matching delete.

Also: page faults are a hidden kind of allocation. The table's constructor writes every slot, so all its pages fault in at startup. The input file's pages fault in on first touch; `MADV_SEQUENTIAL` makes the kernel read ahead.

### MappedFile: RAII and move semantics

- **The destructor unmaps.** The descriptor is closed right after `mmap`; the mapping keeps the file alive.
- **Copy is deleted.** Two owners would both `munmap` the same memory, the mmap version of a double free.
- **Moves use `std::exchange`.** It takes the other object's pointer and leaves it null, so the moved-from destructor does nothing.
- **Move assignment releases the current mapping first**, or it leaks. It also checks for self-assignment.
- **Exceptions are fine here.** It's setup code: if the file can't be opened, stop.

### Testing strategy

| Technique | Catches |
|-----------|---------|
| Bytes written by hand from the spec | Offset bugs that the encoder and parser share. A round trip can't catch those: both sides would be wrong in the same way |
| Round trip (encode → parse → `==`) | Field mix-ups; `operator==` is `= default` |
| Edge cases | Truncation at every byte, zero length, bad side, `F` cut to `A`'s length, unaligned loads |
| Collisions built on purpose | Brute-force keys with a chosen home slot to test backward shift: chain head, two chains running together, wrap-around at the end |
| Randomised differential test | 1M random operations on `OrderTable` vs `std::unordered_map` |
| Differential test against `ReferenceBook` | 500k synthetic messages; every level of every symbol compared every 10k messages |
| Sanitizers | All of the above under ASan+UBSan and TSan |

### Results (synthetic feeds, Intel Xeon @ 2.1 GHz cloud VM, GCC 13, `-O2`, pinned to one core, median of 5)

| | Parse only | Parse + MarketBook | Parse + std::map ReferenceBook |
|---|---|---|---|
| small: 4k live orders, table ≈ 400 KB (fits in L2) | 15.2 ns | 48.8 ns | 103.3 ns |
| large: 500k live orders, table ≈ 48 MB (doesn't fit in L2) | 15.0 ns | 150.0 ns | 338.9 ns |

How to read it:

- **Parse-only here (15 ns) is above the in-cache 11–12 ns.** These feeds are 60 MB and 240 MB, so they stream from memory, on top of the mispredicted type jump.
- **The large case is memory-bound.** Each message makes about 1–2 random accesses into a 48 MB table. On this host it fits in the 260 MB L3, but not the 2 MB L2.
- **TLB misses add to it.** Transparent huge pages are set to `madvise` here, so the table uses 4 KB pages: 12,000 of them, far more than the TLB can map, so most lookups also walk the page table. Huge pages for the table (`madvise(MADV_HUGEPAGE)` on a 2 MB-aligned allocation) are a stage 5 experiment.
- **Our book is about 2.1–2.3× faster than the `std::map`/`unordered_map` version.** The gap will look different on real data. In real feeds, deletes cluster on recent orders near the top of the book; the synthetic feed picks uniformly at random among live orders.

### C++ features used in this stage

- `std::span` (C++20): pointer + length passed as one value
- `std::byte` (C++17): raw bytes, no accidental arithmetic
- `std::endian` (C++20) in a `static_assert`
- `__builtin_bswap*`; `std::byteswap` replaces them in C++23
- Designated initializers (C++20): `AddOrder{.hdr = ..., .order_ref = ...}`. Fields must be in declaration order. GCC's `-Wmissing-field-initializers` wants every field named.
- `bool operator==(const T&) const = default;` (C++20)
- Concepts and `requires` expressions; `if constexpr`; constrained templates (`template <typename M> requires Handles<MarketBook, M>`)
- `[[likely]]` / `[[unlikely]]` (C++20); `[[gnu::always_inline]]`; `[[nodiscard]]`
- `std::bit_ceil`, `std::countr_zero` (C++20 `<bit>`)
- `std::optional` for return values that may be absent
- `std::from_chars` (C++17): number parsing with no exceptions, locale or allocation
- RAII, deleted copy, move constructor and assignment, `std::exchange`
- Replacing global `operator new`/`delete`

### Common mistakes from this stage

1. Casting a byte pointer to an int pointer to read a field (UB).
2. Reading 8 bytes for a 6-byte field.
3. `off + n <= size` bounds checks that can overflow.
4. Casting an unchecked byte to an enum.
5. Keeping an `OrderEntry*` after `erase()`, or a pointer, reference or span into a `std::vector` after it's modified.
6. Tombstone deletion in a hash table that sees a delete for every insert.
7. Taking the *low* bits of a multiplicative hash.
8. Assuming `inline` means inlined. Check the binary.
9. Integer promotion. `uint16_t + 1` is an `int`, so `2 + load_be16(p)` added to a `size_t` is a signed/unsigned mix. `-Wsign-conversion` caught this in our test code.
10. A no-allocation test that counts setup, or misses the `nothrow`/array forms of `new`.
11. A benchmark that changes two variables at once.

### Interview questions (stage 1)

1. Why is `*reinterpret_cast<const uint32_t*>(buf + 32)` wrong for reading an ITCH price? What do you write instead, and what does it compile to on x86?
2. The order table uses linear probing. What happens over a trading day if deletes leave tombstones instead of shifting entries back? Why keep the table at most half full, and why take the *top* bits of the multiplicative hash?
3. Why is a sorted `std::vector` with the best price at the back faster than `std::map` for price levels? Describe a market where it would be slower.
4. How do we know the hot path never allocates? Describe both ways the first version of that test was wrong, and what each mistake would have hidden.
5. With the feed in cache, parsing costs about 3 ns per message when message types arrive in a predictable order and about 11–12 ns when they're random. Explain the difference, and why just following the length prefixes has a floor of about 2.6 ns.

#### Model answers (stage 1)

**1. Reading a price with `reinterpret_cast`.**
- It is undefined behaviour twice over:
  - The address may be misaligned: the field sits at offset 32 of a message that can start anywhere.
  - It reads `std::byte` objects through a `uint32_t` lvalue, which breaks strict aliasing.
- Write `std::memcpy(&v, p, 4)` followed by `__builtin_bswap32(v)` (`std::byteswap` in C++23).
- That compiles to `mov eax, [rdi+32]; bswap eax`, or a single `movbe` with `-march=haswell`.

**2. Tombstones, load factor, top bits.**
- **Tombstones:** every delete leaves a marker that lookups have to probe past. Over ~100M deletes a day they pile up, probe sequences get longer and longer, and fixing it means a rehash, which is a pause.
- **Half full:** the expected probes for a miss in linear probing grow like `1/(1-α)²`. That's about 2.5 probes at α = 0.5 and about 50 at α = 0.9.
- **Top bits:** a product's low bits depend only on the key's low bits, while its top bits mix every key bit. So the top bits spread consecutive order references evenly over the table.

**3. Sorted vector vs `std::map`.**
- Updates near the top of the book touch the end of the vector: a short, predictable linear scan, a few 16-byte elements shifted, contiguous memory, and no allocation.
- `std::map` allocates a node per new level and chases pointers on every lookup, and each pointer load can miss the cache.
- The vector would be slower in a book where activity is spread across hundreds of levels, such as an illiquid stock with a deep, active book: every scan and every shift becomes O(depth).

**4. Proving the hot path doesn't allocate.**
- Preallocate at setup, refuse instead of growing (`table_full`), and count any growth (`level_growth_events`).
- Then a test replaces global `operator new` and requires zero allocations during trading. It also checks the checker (a known allocation must be counted).
- The two mistakes:
  - **It counted setup as trading.** The stock directory reserves (8 symbols × 2 sides) made the test fail. Loosening the threshold to pass would have hidden real allocations.
  - **It didn't replace the `nothrow` and array forms.** Under ASan those bypass the counter, so allocations through them were invisible and the test could pass while the code allocated. ASan's alloc-dealloc mismatch report exposed it.

**5. 3 ns vs 11–12 ns, and the 2.6 ns floor.**
- The `switch` is an indirect jump through a table. The branch predictor learns its target from history, so predictable types cost almost nothing.
- With random types, about one mispredict per message (a pipeline flush of 15–20 cycles) adds about 8 ns.
- The 2.6 ns floor is a dependency chain: each message's address comes from the previous message's length, so every iteration waits for a load (~5 cycles from L1), a byte swap and an add. Consecutive messages can't overlap.

---

## Stage 2: lock-free SPSC ring buffer and the two-thread pipeline

### What runs where

```
 feed thread (core 2)                                 strategy thread (core 3)
 parse ITCH → MarketBook → snapshot top 5 levels      pop → consume(update)
                 │  (subscribed symbols, if changed)          ▲
                 └──► SpscRing<BookUpdate, 4096> ─────────────┘
                      128-byte slots, 512 KB, lock-free
```

| File | Role |
|------|------|
| `concurrency/spsc_ring.hpp` | the lock-free ring |
| `common/cpu.hpp` | `cpu_relax` (PAUSE), `pin_current_thread`, `rdtsc`, `TscClock`, `CachePadded<T>` |
| `common/latency_recorder.hpp` | preallocated samples, percentiles at the end |
| `feed/book_update.hpp` | the 128-byte snapshot that crosses the ring |
| `feed/feed_handler.hpp` | ITCH handler: book + subscriptions + publish |
| `feed/pipeline.hpp` | starts the strategy thread, runs the feed, shuts down cleanly |
| `apps/pipeline.cpp` | runs it on a file and reports latency percentiles |

### The SPSC ring, piece by piece

- **Single producer, single consumer.** Each index has exactly one writer, so plain atomic loads and stores are enough: no compare-and-swap, no retry loop, no lock. An MPMC queue needs CAS, and under contention a CAS loop costs far more than these stores.
- **Power-of-two capacity, known at compile time.** `index & (N-1)` is a single AND.
- **Counters that only increase.** Full is `write - read == N`, empty is `write == read`, and all N slots are usable. Wrapping indices can't tell full from empty without wasting a slot.
- **Trivially copyable `T`.** A slot is a plain copy, with no constructors or destructors.
- **Copy deleted.** Both threads hold a reference to the same ring, so it must never move.
- **A big object.** 4096 × 128 B = 512 KB, so allocate it once with `make_unique`, never on a thread's stack.

### Memory ordering: the core of the ring

| Operation | Ordering | Why |
|-----------|----------|-----|
| Producer loads its own `write` | relaxed | Only this thread writes it |
| Producer writes the slot | plain store | The data |
| Producer stores `write + 1` | **release** | Everything written before it (the slot) is visible to whoever acquires this value |
| Consumer loads `write` | **acquire** | Pairs with the release above: the slot is now safe to read |
| Consumer stores `read + 1` | **release** | Its read of the slot is finished before the producer can reuse the slot |
| Producer loads `read` | **acquire** | Pairs with the consumer's release: the slot is now safe to overwrite |

- **Happens-before.** A release store, plus an acquire load that reads the value it stored, form a synchronises-with edge. Every write before the release is then visible after the acquire.
- **Relaxed everywhere is a data race on the slot**, which is undefined behaviour. The compiler may move the slot write after the index store, and an ARM CPU may reorder them itself.
- **On x86 acquire and release are free.** Plain loads already act as acquire and plain stores as release (x86's "TSO" memory model). The ordering costs nothing at run time there; it stops the *compiler* from reordering, and keeps the code correct on ARM.
- **`seq_cst` costs something.** A sequentially consistent store compiles to `xchg` (about 20+ cycles), which this ring doesn't need.

**Proof, not belief:**

- The two-thread stress test pushes 1M items through a 16-slot ring and checks that each arrives once, in order and intact. It runs under TSan.
- A **mutation test**: with the producer's release changed to relaxed, the same test under TSan reports a data race at `try_pop` (the slot read) against `try_push` (the slot write).
- A **broken-ring canary**: a ring with only relaxed operations, which TSan must flag. The first version passed by accident:
  - The consumer never used the values it popped, so the compiler deleted the slot read.
  - With the read gone, there was no race left to detect.
  - Same lesson as the benchmark that measured 0.000 ns: unused results get deleted.

### False sharing, padding and index caching

- **False sharing.** Two cores write different variables that share a 64-byte cache line, so the line bounces between them, roughly 100 ns per transfer, even though no data is actually shared.
- **Padding:** the producer's fields, the consumer's fields and the slot array each start on their own 128-byte block (`alignas(kNoFalseSharing)`).
  - Why 128 and not 64: Intel's spatial prefetcher fetches cache lines in adjacent pairs.
  - `std::hardware_destructive_interference_size` exists, but GCC warns that its value can change with compiler flags, which would silently change our layout.
- **Index caching:** each side keeps a private copy of the other side's index, and rereads the shared one only when its copy says full (producer) or empty (consumer). That saves a cross-core read on most operations.

### What crosses the ring: snapshots, not deltas

- **The strategy needs no book of its own.** All order bookkeeping stays on the feed thread.
- **A snapshot is idempotent.** A dropped snapshot is fixed by the next one. A dropped delta corrupts the receiver's book until a resync.
- **128 bytes, `alignas(64)`:** two whole cache lines, so no two updates share a line in the ring.
- **Conflation:** if the top 5 levels didn't change (for example, an order added at level 8), nothing is sent.
- **Saturation:** a level holding more than 4.29 billion shares shows as `UINT32_MAX`. Saturating is safer than wrapping to a small number.
- **When the ring is full:**
  - **Drop** (the default) counts the update and moves on. A slow strategy must never stall the feed; in stage 3 a stalled feed thread means UDP packets lost in the kernel.
  - **Wait** spins until there is room, which loses nothing, but the feed runs at the strategy's speed.
- **`last_sent` is the last *delivered* snapshot**, not the last one built. If it recorded a dropped snapshot, a book that then stopped changing would never be resent, and the strategy would stay stale forever. There is a test for exactly that.
- **Sequence numbers count every attempted send**, so drops show up as gaps on the strategy side. The integration test checks that gaps plus drops after the last received update equal the feed's drop count. That invariant holds whatever the timing.

### Threads: pinning, spinning, startup and shutdown

- **Pinning.** `pthread_setaffinity_np` keeps each thread on its own core. A thread moved to another core starts with a cold cache.
- **Busy polling with `pause`** (`cpu_relax`).
  - Waking a sleeping thread (a futex or condition variable) costs tens of microseconds, so the strategy thread spins instead, burning its core.
  - PAUSE saves power and helps a hyperthread sibling, but costs about 140 cycles on recent Intel server CPUs. In the experiment it changed throughput by up to 1.9×.
- **Start handshake.** The feed waits until the strategy thread is pinned and running. Before that, thread creation (up to milliseconds) polluted the latency tail.
- **Shutdown.**
  - The feed sets `done` with release.
  - The strategy loads it with acquire, then drains whatever is left before exiting.
  - The pair guarantees every update pushed before `done` is visible to the drain.
- **`std::jthread` (C++20)** joins in its destructor. A `std::thread` that is never joined calls `std::terminate`.

### Three problems found by measuring

| Symptom | Cause | Fix | Result |
|---------|-------|-----|--------|
| Feed at 595 ns/msg vs 60 ns single-threaded | The strategy thread polled `done`, which sat on the same cache line as the `FeedStats` the parser updates every message | `CachePadded<std::atomic<bool>> done` | **104 ns/msg (5.7× faster)** |
| Ring hop p99 13–28 µs | `LatencyRecorder` used `reserve()`, which doesn't touch the memory, so it took a page fault every 512 samples | Write the whole buffer in the constructor | p99 down to 1.5 µs in quiet runs |
| Tails up to 2 ms that varied run to run | The feed started before the strategy thread was running | Start handshake | Startup no longer in the samples |

Each one was a hypothesis tested with a single change before it was kept.

### The machine's noise floor

A thread that only reads the TSC in a loop, pinned to core 2 or 3 of this cloud VM, was paused for:

- more than 10 µs: about 2,600 times in 2 s
- more than 100 µs: about 50 times
- more than 1 ms: up to 8 times, the longest 5.1 ms

No steal time was recorded, but the hypervisor and timer interrupts still take the core. So on this machine only the median and p90 of the pipeline's latency are meaningful; p99 and above measure the VM.

On a production Linux box you would:

- reserve cores for the hot threads (`isolcpus`)
- turn off the timer tick on them (`nohz_full`)
- move interrupts elsewhere (IRQ affinity)
- disable deep C-states

**Measure the machine before blaming the code.**

### Results (cloud VM, Xeon @ 2.1 GHz, producer core 2, consumer core 3)

Pipeline, 2M synthetic messages, 3 symbols subscribed, 5 runs:

- Feed: 91–101 ns per message (the single-threaded baseline is 60 ns).
- 229,627 updates sent, with 0 drops and 0 gaps.
- Ring hop (publish to receive, TSC on two cores): **p50 339–369 ns, p90 470–537 ns.** p99 ranged from 1.5 µs to 2 ms (machine noise, see above).

Ring micro-benchmarks, ranges over 4 runs:

| Variant | Throughput, ns/item | Round trip p50 | Round trip p99 |
|---------|---------------------|----------------|----------------|
| SpscRing (real) | 52 – 84 | **537 – 611 ns** | **798 – 835 ns** |
| Unpadded | 83 – 128 | 660 – 826 ns | 911 – 1,117 ns |
| No index caching | 33 – 71 | 686 – 757 ns | 846 – 931 ns |
| `std::mutex` ring | 170 – 188 | 2,255 – 2,637 ns | **26,200 – 26,700 ns** |

How to read it:

- **Latency results are consistent across every run.** The real ring has the lowest round trip; unpadded and no-caching each add 10–40%. The mutex is about 4× slower at the median and about 30× at p99. A lock means the losing thread can end up waiting in the kernel, and that shows up in the tail.
- **The throughput results are not consistent on this VM**, except that the mutex is always slowest. A control (the same settings as the real ring, built from the benchmark's own variant class) matched the real ring within the noise, so the harness is sound.
- **Index caching did not improve streaming throughput here.** The no-cache variant was faster in every run. A likely reason is that in streaming the producer and consumer end up next to each other in the ring, so the *slot* cache lines bounce between cores, and caching only saves *index* line transfers.
- **Open question:** re-measure on bare metal, with `perf c2c` to show which cache lines bounce.

### TSC across cores

- One-way latency compares a timestamp taken on core 2 with one taken on core 3. That's valid only if the cores' TSCs are synchronised, which is true here (`constant_tsc`, `nonstop_tsc`, `tsc_known_freq`).
- Not every machine guarantees it, so the strategy counts "clock skew" (a receive time earlier than the publish time) instead of recording a huge bogus latency.
- The round-trip benchmark avoids the issue by timing on one core.

### No allocation, again

`NoAllocation.FeedHandlerPublishingAllocatesNothing` covers the feed thread's whole hot path: parse, book update, snapshot, comparison and push, with every symbol subscribed. It also runs the drop path, because no consumer runs. It makes 0 allocations.

### C++ features used in this stage

- `std::atomic`: `load` and `store` with `memory_order_relaxed`, `acquire` and `release`; `is_always_lock_free`
- `alignas` on structs; the template `CachePadded<T>`
- `static_assert` with `std::has_single_bit` and `std::is_trivially_copyable_v`
- `std::jthread` (C++20); lambdas capturing by reference; `std::bitset`
- `if constexpr` to build benchmark variants from one template
- Preprocessor trap: commas inside template arguments split macro arguments (`EXPECT_DEATH(... BrokenRing<T, 16> ...)`)
- Name lookup: GoogleTest's `Test::Setup()` member hid a namespace-level `struct Setup` inside a `TEST` body

### Common mistakes from this stage

1. Using `relaxed` for the index that publishes data, or `seq_cst` everywhere "to be safe".
2. Flags, counters or indices of different threads on the same cache line.
3. Reading the other thread's index on every operation.
4. Measuring latency with a cold `reserve()`d buffer. `reserve` is not a prefault.
5. Starting the measurement before every thread is running.
6. Reporting p99 from a noisy machine without measuring the machine's own noise floor.
7. Recording the last *built* message as "sent" when it was dropped.
8. A concurrency test whose racy read the optimiser deleted.
9. Comparing TSC values from different cores without knowing the TSCs are synchronised.

### Interview questions (stage 2)

1. Walk through `try_push` and `try_pop`. Which loads and stores need acquire or release, which can be relaxed, and what breaks if everything is relaxed? Why would the broken version probably still pass a test on x86?
2. What is false sharing? Describe the bug in `run_pipeline`: how it showed up, how it was confirmed, and the before/after numbers. Why pad to 128 bytes rather than 64?
3. Why does the feed send top-of-book snapshots instead of raw messages or deltas? What happens when the ring is full under each policy, and why must `last_sent` be the last *delivered* snapshot?
4. The ring hop has a p50 of ~350 ns but a p99 anywhere from 1.5 µs to 2 ms. How did we separate what the code costs from what the machine adds, and what would you change on a production server?
5. Why does a lock-free SPSC ring beat a mutex-protected queue, especially at p99? Index caching improved round-trip latency but not streaming throughput here. Give a plausible reason.

#### Model answers (stage 2)

**1. The orderings in `try_push` and `try_pop`.**

| Operation | Ordering |
|-----------|----------|
| Each side loads its own index | relaxed (it is the only writer) |
| Producer writes the slot | plain store |
| Producer stores `write` | **release** |
| Consumer loads `write` | **acquire** |
| Consumer stores `read` | **release** |
| Producer loads `read` | **acquire** |

- **All relaxed:** there's no happens-before between writing a slot and reading it, so it is a data race and undefined behaviour.
  - The compiler may move the slot store after the index store, and ARM may reorder them in hardware.
  - The consumer can then read a stale or half-written slot, or the producer can overwrite a slot that is still being read.
- **Why it might pass on x86:** x86 is TSO. It never reorders a store with another store, or a load with another load. So only the *compiler* can break it, which is why the bug can hide for a long time.
- TSan checks the C++ memory model rather than the hardware, so it flags it, as our mutation test showed.

**2. False sharing.**
- Two cores write *different* variables that sit on the same cache line. The coherence protocol (MESI) moves the whole line to whichever core writes, invalidating the other core's copy, so every write costs a line transfer.
- **The bug:** the strategy thread polled `done` (whenever the ring was empty), and `done` sat next to the `FeedStats` the feed thread updates on every message.
  - Symptom: 595 ns per message against 60 ns single-threaded.
  - Confirmed by changing one thing: `done` moved to its own 128-byte block gave 104 ns.
- **128 rather than 64:** Intel's adjacent-line prefetcher fetches lines in 128-byte pairs, so a neighbour in the paired line still interferes.

**3. Snapshots, the full-ring policies, `last_sent`.**
- **Why snapshots:**
  - The strategy needs no book of its own.
  - Snapshots are idempotent, so a drop is harmless: the next snapshot replaces it.
  - Only the subscribed symbols' changes cross the ring, not every message in the market.
  - Deltas need reliable delivery plus a resync mechanism.
- **Full ring:** Drop counts the update, and the strategy sees a sequence gap. Wait spins until there's room, so nothing is lost, but the feed slows down; on a network feed that means the kernel starts dropping packets.
- **`last_sent` must be the last *delivered* snapshot.** If it recorded a dropped one, a book that then stopped changing would look "unchanged" forever and never be resent.

**4. Separating the code's cost from the machine's.**
- Each suspect was a hypothesis tested with one change: false sharing, page faults, the startup transient.
- Then the machine's own noise floor: a pinned loop doing nothing but reading the TSC was paused for more than 1 ms several times in 2 s. So the tails here measure the VM, not the code.
- On a production server:
  - bare metal, not a VM
  - reserve cores for the hot threads (`isolcpus`, `nohz_full`, `rcu_nocbs`) and move interrupts off them (IRQ affinity)
  - the `performance` frequency governor, with deep C-states disabled
  - huge pages, `mlockall`, and everything prefaulted
  - no system calls on the hot path

**5. Lock-free ring vs mutex, and why caching helped latency only.**
- **The mutex:** every operation is an atomic read-modify-write on a shared lock word, and the producer and consumer serialise on it. Under contention the losing thread can end up sleeping in the kernel (futex), and waking it costs tens of µs. That's the p99 of 26 µs against 0.8 µs.
- **Caching helped the round trip** because each push skipped one cross-core read of the other side's index: one fewer cache-line transfer per hop.
- **It didn't help streaming here** because the producer and consumer work on neighbouring slots, so the slot cache lines bouncing between cores dominate, and the cached index doesn't touch that. PAUSE timing adds noise on top.

---

## Stage 3: UDP multicast replay

### What runs where

```
replay_server (process, core 1)                 feed_handler (process)
 ITCH file → MoldUDP64 packets, paced by          network thread (core 2):
 timestamps ──► multicast 239.255.1.1 (line A) ──►  recv A/B → merge by sequence → gaps/dups
            └─► multicast 239.255.1.2 (line B) ──►  → ITCH parse → book → snapshot → ring
                                                  strategy thread (core 3): pop, measure
```

| File | Role |
|------|------|
| `net/moldudp64.hpp` | packet format: header decode, bounds-checked message walk, `PacketBuilder` |
| `net/sequence_tracker.hpp` | new / duplicate / overlap / gap decision per packet |
| `net/udp_socket.hpp`, `src/net/udp_socket.cpp` | RAII socket: bind, multicast join, buffers, non-blocking recv, kernel counters |
| `net/mold_receiver.hpp` | busy-poll loop, A/B merge, hands messages to the ITCH parser |
| `itch/framing.hpp` | walks a BinaryFILE without parsing (for the replayer) |
| `feed/pipeline.hpp` | now takes any source: file or network |
| `apps/replay_server.cpp`, `apps/feed_handler.cpp` | the two processes |

### MoldUDP64, the packet format Nasdaq uses

- **Header** (20 bytes): session (10 ASCII bytes), the sequence number of the first message (8 bytes, BE), and the message count (2 bytes, BE). Then each message as `[2-byte length][bytes]`.
- **Sequence numbers count messages, not packets.** A packet `(seq s, count n)` carries messages s .. s+n-1, so the next packet should start at s+n. That's how loss is detected.
- **Heartbeat** (count 0): sent while idle, carrying the *next* sequence number. That reveals messages lost at the end of a burst, which no later data packet would otherwise expose.
- **End of session** (count 0xFFFF): sent three times, because a single lost copy would leave receivers waiting for their timeout. It also carries the next sequence number, so it reveals loss at the very end.
- **Every length comes from the network.** Each block is bounds-checked against the packet, as in the BinaryFILE parser.

### Packet size and the MTU

- A UDP datagram larger than the path's MTU is split into IP fragments, and losing **any** fragment loses the whole datagram. Feeds never fragment.
- The payload limit is MTU − 20 (IP header) − 8 (UDP header): **1472 bytes** for the usual 1500, and **1372** in this container, whose `eth0` MTU is 1400.

### The replay server: pacing like an exchange

- Each message has a due time: `start + (timestamp − first timestamp) / speed`.
- If the next message isn't due yet (more than 1 µs away), the current packet goes out *now*, so messages are never held back to fill a packet. Then the server waits.
- Messages due within 1 µs of each other share a packet: 6.1 per packet at real time, 44.3 with no pacing.
- **Long waits sleep; short ones spin.** Spinning through a 30-second quiet spell in a real day file would just burn a core. Heartbeats go out during long waits.
- **Measured pacing:** p50 about 1 µs late, but p99 0.5–8 ms. About 165k `sendto` calls per second, each costing a few µs (multicast loopback also copies the packet to the local receiver inside the call), uses up one core.
- **Simulated loss:** `--drop-a` and `--drop-b` drop packets on purpose, from a seeded RNG, so runs are repeatable.

### Sockets: what each option does

- **`IP_ADD_MEMBERSHIP`:** joins the group. The kernel (and switches, via IGMP) then deliver its traffic here.
- **Binding to the group address** rather than `0.0.0.0` filters out other groups that use the same port.
- **`SO_REUSEADDR`:** several receivers on one host can share a group and port.
- **`IP_MULTICAST_TTL 1`** keeps packets on the local network. **`IP_MULTICAST_LOOP 1`** delivers to receivers on the sending host, which our testing needs.
- **`SO_RCVBUF`:** the burst absorber.
  - The kernel caps the request at `net.core.rmem_max` (4 MB here), then *doubles* it for its own bookkeeping, so we asked for 4 MB and were granted 8 MB.
  - When the buffer overflows, the kernel drops datagrams and counts them in `RcvbufErrors` (`/proc/net/snmp`).
- **`MSG_DONTWAIT`** makes a call non-blocking; **`MSG_TRUNC`** returns a datagram's real size even when the buffer was too small.

### The receiver: busy-polling and A/B arbitration

- **Busy-polling** (`recv` with `MSG_DONTWAIT` in a spin loop) costs one core at 100%, but no wake-up delay (measured below).
- **Timeouts:** reading the clock costs ~25 ns, so the receiver checks its timeouts only every 64k empty polls.
- **A/B arbitration:**
  - The exchange sends identical packets on two multicast groups over separate network paths, and the receiver keeps the first copy of each.
  - Implemented as a **merge**: each line holds at most one waiting packet, and the lower sequence number goes first.
  - If that packet would open a gap while the other line has nothing waiting, the receiver gives the other line `arbitration_window_us` (50 µs) before declaring the gap.
  - **The bug this fixed:** reading line A first made a packet A lost look lost even when B's copy was already waiting. Measured with 1% independent loss per line: **99 gaps** before the merge; **12 and 6** after, against an expected ≈ 14–15 (packets × 1% × 1%).
  - **Window trade-off:** longer windows survive more lag between the lines; shorter ones delay processing less when a packet really is lost on both. Most real gaps need no wait at all: if both lines' next packets are past the missing number, the gap is certain at once.
- **Known start vs late join:** with `first_seq = 1`, a lost *first* packet is a gap. Without it, the first packet seen becomes "the start" and the loss is invisible. The test `ArbitrationLosesOnlyPacketsBothLinesLost` caught exactly this: packet 0 was lost on both lines. Use `--late-join` only when joining a session already in progress.

### What loss does to the book

- One line with 1% loss: 3,943 gaps and 19,871 messages lost, giving **13,949 "unknown order"** anomalies and a wrong book. SYN3's best bid showed 20,998 shares where the truth is 5,851: ghost orders whose deletes never arrived.
- The strategy's view "matched", but it matched a corrupted book. Consistency is not correctness.
- **Production recovery:**
  - request the missing range from the exchange's retransmission server (MoldUDP64 has one)
  - or rebuild from the exchange's snapshot service (Nasdaq's is GLIMPSE) and replay from there
  - meanwhile, mark the symbol's book untrustworthy so the strategy doesn't trade on it

### Telling our losses from the network's

- No pacing into a 64 KB receive buffer: the kernel counted **4,343** buffer overflows, and 45,100 packets sent minus 40,758 received is 4,342 (plus the end-of-session packet).
- So `RcvbufErrors` attributes every loss to *our* socket being too slow, not to the wire. With the full 8 MB buffer the same run lost **0**.

### Benchmark: what the kernel costs (two pinned cores, 64-byte packets)

| Path | Round trip p50 | Round trip p99 |
|------|----------------|----------------|
| SPSC ring (stage 2), never enters the kernel | 0.54–0.61 µs | 0.80–0.84 µs |
| UDP loopback, busy-poll | **3.8–3.9 µs** | 8.0–8.7 µs |
| UDP loopback, blocking (thread sleeps in poll) | **28–29 µs** | 62–68 µs |

- **Sleeping costs about 7.5×.** The kernel waking the thread costs roughly 24 µs per round trip.
- **The kernel network stack costs about 6.5× the ring, even busy-polling.** Hence **kernel bypass:** Solarflare/OpenOnload, ef_vi, DPDK and AF_XDP have the network card write packets straight into the application's memory, with no system calls.
- **Smaller steps inside the kernel:** `SO_BUSY_POLL`; `recvmmsg`/`sendmmsg` (several packets per system call); hardware receive timestamps (`SO_TIMESTAMPING`); interrupt coalescing settings; pinning the NIC's interrupts to a chosen core.

### End-to-end results

- **Real time:** 2,000,009 messages in 327,539 packets, 0 gaps, 0 kernel overflows. The final books are identical to stage 2's file-based run, and the ring hop is p50 272 ns, p90 400 ns.
- **No pacing:** the sender reached 7.76 M messages/s (45,100 full packets), and the busy-polling receiver kept up with 0 gaps.

### Problems found this stage

| Problem | Found by | Fix |
|---------|----------|-----|
| A/B: packets one line lost but the other delivered were declared lost (99 gaps vs ~15) | Measuring against the expected loss rate | Merge by sequence, with a wait window |
| A lost first packet was invisible | `Udp.ArbitrationLosesOnlyPacketsBothLinesLost` (off by exactly one packet's 42 messages) | `first_seq` (known start) vs `--late-join` |
| End of session didn't reveal loss at the very end | Code review | End of session goes through the tracker too |
| Idle timeout measured from the start of the run, not the last packet | Code review | Measure each quiet spell |
| A flag taking no value, given last, failed argument parsing | Code review | Handle value-less flags first |
| `EXPECT_EQ` as the body of an unbraced `if` | `-Wdangling-else` | Braces (the macro contains its own if/else) |

### Common mistakes from this stage

1. Treating UDP as reliable. Sequence numbers, gap counters and a recovery plan are mandatory.
2. Datagrams bigger than the MTU (fragmentation).
3. Starting the sender before the receiver has joined. UDP keeps nothing for later.
4. Trusting any length field that came from the network.
5. Blocking receives on the hot path.
6. A/B arbitration that reads one line ahead of the other.
7. "First packet seen = start", when the start is actually known.
8. Not checking `RcvbufErrors`, then blaming the network for your own slow consumer.
9. Assuming `SO_RCVBUF` gives what you asked for. It is capped by `rmem_max`, and the reported size is doubled.

### Interview questions (stage 3)

1. Describe MoldUDP64's header. How does a receiver detect lost packets, including loss at the end of a burst and loss of the very first packet? Why does the exchange send heartbeats?
2. What is A/B line arbitration? Why did the first version report 99 gaps when only about 15 packets were lost on both lines, and how does the merge with a wait window fix it? What is the trade-off in choosing the window's length?
3. Why do feeds keep packets below the MTU? What happens to a UDP datagram larger than the MTU, and where did our 1,372-byte limit come from?
4. The receiver busy-polls with non-blocking `recv`. What did the benchmark show for busy-poll vs blocking, and vs the in-process ring? How do trading firms go faster than the kernel's UDP stack?
5. A single line loses 1% of its packets. What happens to the order book, and how would you detect and recover in production? How did we tell our own socket buffer overflowing apart from loss on the network?
