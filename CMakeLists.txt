cmake_minimum_required(VERSION 3.25)

project(hft_lob
  VERSION 0.1.0
  DESCRIPTION "ITCH 5.0 feed handler, limit order book and low-latency inference"
  LANGUAGES CXX)

# ---- Language ----------------------------------------------------------------
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)   # fail instead of silently using C++17
set(CMAKE_CXX_EXTENSIONS OFF)         # -std=c++20, not -std=gnu++20

# compile_commands.json for clangd / clang-tidy / IDEs.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ---- Build type --------------------------------------------------------------
# An empty CMAKE_BUILD_TYPE means no -O flag at all, i.e. an unoptimised build.
# Benchmarking that by accident is a classic mistake, so pick a sane default.
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Build type" FORCE)
  message(STATUS "No build type given, defaulting to RelWithDebInfo (-O2 -g -DNDEBUG)")
endif()

# ---- Options -----------------------------------------------------------------
option(HFT_BUILD_TESTS      "Build unit tests"                     ON)
option(HFT_BUILD_BENCHMARKS "Build Google Benchmark binaries"      ON)
option(HFT_WERROR           "Treat warnings in our code as errors" OFF)
option(HFT_MARCH_NATIVE     "Optimise for this machine's CPU only" OFF)
set(HFT_SANITIZER "none" CACHE STRING "Sanitizer build: none | asan | tsan")
set_property(CACHE HFT_SANITIZER PROPERTY STRINGS none asan tsan)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

# Order matters: global flags must be set before the dependencies are added,
# so GoogleTest and Google Benchmark are compiled with them too.
include(Sanitizers)
if(HFT_MARCH_NATIVE)
  add_compile_options(-march=native)
endif()
include(CompilerWarnings)
include(Dependencies)

# ---- Targets -----------------------------------------------------------------
if(HFT_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()

if(HFT_BUILD_BENCHMARKS)
  add_subdirectory(bench)
endif()
