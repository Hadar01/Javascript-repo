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

*(Answers are added once you've attempted them.)*
