# hft_add_benchmark(<name> SOURCES <file>... [LIBS <target>...])
#
# benchmark::benchmark_main supplies main(), which parses the --benchmark_*
# command-line flags and runs every registered benchmark.
function(hft_add_benchmark name)
  cmake_parse_arguments(ARG "" "" "SOURCES;LIBS" ${ARGN})
  add_executable(${name} ${ARG_SOURCES})
  target_link_libraries(${name} PRIVATE ${ARG_LIBS} hft::warnings benchmark::benchmark_main)
endfunction()

hft_add_benchmark(clock_bench SOURCES clock_bench.cpp)
hft_add_benchmark(itch_bench  SOURCES itch_bench.cpp  LIBS hft::core hft::testsupport)
hft_add_benchmark(spsc_bench  SOURCES spsc_bench.cpp  LIBS hft::core)
hft_add_benchmark(udp_bench   SOURCES udp_bench.cpp   LIBS hft::core)
hft_add_benchmark(model_bench SOURCES model_bench.cpp LIBS hft::core)
# The model and inputs python/train.py exported.
target_compile_definitions(model_bench PRIVATE HFT_TEST_DATA_DIR="${PROJECT_SOURCE_DIR}/tests/data")
