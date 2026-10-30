include(GoogleTest)

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
