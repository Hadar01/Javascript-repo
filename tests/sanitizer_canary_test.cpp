// Canary tests for the sanitizer builds.
//
// Each test commits one deliberate bug inside EXPECT_DEATH and checks that the
// matching sanitizer kills the process with the expected report. If a canary
// fails in a sanitizer build, the flags never reached the compiler, and every
// "clean" run of the other tests proved nothing.
//
// In builds without the sanitizer, the canary is skipped.

#include <gtest/gtest.h>

#include <climits>
#include <cstddef>
#include <thread>

// GCC predefines __SANITIZE_ADDRESS__ / __SANITIZE_THREAD__. Clang only
// reports sanitizers through __has_feature.
#if defined(__SANITIZE_ADDRESS__)
#define HFT_HAS_ASAN 1
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
#define HFT_HAS_ASAN 1
#endif
#endif

#if defined(__SANITIZE_THREAD__)
#define HFT_HAS_TSAN 1
#elif defined(__has_feature)
#if __has_feature(thread_sanitizer)
#define HFT_HAS_TSAN 1
#endif
#endif

#if defined(HFT_HAS_TSAN)
// TSan calls this hook at startup to get its default options. By default TSan
// prints a race and keeps running, so the death test would see a process
// that "did not die". TSAN_OPTIONS from the environment still overrides this.
extern "C" const char* __tsan_default_options() { return "halt_on_error=1"; }
#endif

// The volatile locals below stop the compiler from seeing the bug at compile
// time. Otherwise it may warn (and -Werror fails the build) or, because the
// code is UB, delete it. We want the bug to happen at run time.

TEST(SanitizerCanary, AsanCatchesHeapBufferOverflow) {
#if !defined(HFT_HAS_ASAN)
  GTEST_SKIP() << "not an ASan build";
#else
  // `p` is itself volatile so the compiler can't trace it back to the
  // new int[4]. If it could, UBSan's object-size check would catch the bug
  // first, and we'd learn nothing about whether ASan is on.
  EXPECT_DEATH(
      {
        volatile std::size_t index = 4;
        int* volatile p = new int[4];
        p[index] = 1;  // writes one element past the end
        delete[] p;
      },
      "heap-buffer-overflow");
#endif
}

TEST(SanitizerCanary, UbsanCatchesSignedOverflow) {
#if !defined(HFT_HAS_ASAN)  // our asan build always enables UBSan with it
  GTEST_SKIP() << "not an ASan+UBSan build";
#else
  EXPECT_DEATH(
      {
        volatile int x = INT_MAX;
        volatile int y = x + 1;  // signed overflow is undefined behaviour
        (void)y;
      },
      "signed integer overflow");
#endif
}

TEST(SanitizerCanary, TsanCatchesDataRace) {
#if !defined(HFT_HAS_TSAN)
  GTEST_SKIP() << "not a TSan build";
#else
  EXPECT_DEATH(
      {
        int counter = 0;  // plain int: no atomic, no mutex
        std::thread t([&counter] { ++counter; });
        ++counter;  // races with the increment on the other thread
        t.join();
      },
      "data race");
#endif
}
