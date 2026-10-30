include(GoogleTest)

# Shared test helpers (the reference book). INTERFACE: only an include path.
# Benchmarks use it too, for the naive baseline.
add_library(hft_testsupport INTERFACE)
add_library(hft::testsupport ALIAS hft_testsupport)
target_include_directories(hft_testsupport INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/support)

# hft_add_test(<name> SOURCES <file>... [LIBS <target>...])
#
# One test executable per component, so a failure or a sanitizer report points
# straight at the component that caused it.
function(hft_add_test name)
  cmake_parse_arguments(ARG "" "" "SOURCES;LIBS" ${ARGN})
  add_executable(${name} ${ARG_SOURCES})
  target_link_libraries(${name} PRIVATE ${ARG_LIBS} hft::warnings GTest::gtest_main)
  # PRE_TEST: ask the binary for its test list when ctest runs, not as a build
  # step. Otherwise a binary that can't start (e.g. a sanitizer runtime
  # problem) fails the build with a confusing error instead of failing a test.
  gtest_discover_tests(${name} DISCOVERY_MODE PRE_TEST)
endfunction()

hft_add_test(sanitizer_canary_test SOURCES sanitizer_canary_test.cpp)
hft_add_test(wire_test         SOURCES wire_test.cpp         LIBS hft::core)
hft_add_test(parser_test       SOURCES parser_test.cpp       LIBS hft::core)
hft_add_test(order_table_test  SOURCES order_table_test.cpp  LIBS hft::core)
hft_add_test(order_book_test   SOURCES order_book_test.cpp   LIBS hft::core)
hft_add_test(market_book_test  SOURCES market_book_test.cpp  LIBS hft::core hft::testsupport)
hft_add_test(mapped_file_test  SOURCES mapped_file_test.cpp  LIBS hft::core)
# Its own executable: it replaces the global operator new.
hft_add_test(no_alloc_test     SOURCES no_alloc_test.cpp     LIBS hft::core)
