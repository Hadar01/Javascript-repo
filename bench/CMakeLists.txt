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
