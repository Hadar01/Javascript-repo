# Third-party dependencies, fetched and built from source at configure time.
#
# Pinned to release tags so every build uses the same code. Building them from
# source (instead of using distro packages) also means they get the same
# sanitizer flags as our code.
#
# SYSTEM marks their headers as system headers, so the compiler doesn't apply
# our warning flags to them when we #include them.

include(FetchContent)

if(HFT_BUILD_TESTS)
  set(BUILD_GMOCK   OFF)   # we only need gtest, not gmock
  set(INSTALL_GTEST OFF)
  FetchContent_Declare(googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG        v1.17.0
    GIT_SHALLOW    TRUE
    SYSTEM)
  FetchContent_MakeAvailable(googletest)
endif()

if(HFT_BUILD_BENCHMARKS)
  set(BENCHMARK_ENABLE_TESTING OFF)   # its own tests would also pull in gtest
  set(BENCHMARK_ENABLE_INSTALL OFF)
  set(BENCHMARK_INSTALL_DOCS   OFF)
  set(BENCHMARK_ENABLE_WERROR  OFF)   # a newer compiler shouldn't break our build
  FetchContent_Declare(benchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG        v1.9.4
    GIT_SHALLOW    TRUE
    SYSTEM)
  FetchContent_MakeAvailable(benchmark)
endif()
