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
