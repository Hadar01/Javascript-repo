# hft_core: the project's library.
#
# Most of it is header-only (include/hft/...): the hot-path code lives in
# headers so it can be inlined into its callers. The .cpp files here are the
# parts that never run on the hot path.
add_library(hft_core
  common/cpu.cpp
  common/mapped_file.cpp
  itch/synthetic.cpp
  net/udp_socket.cpp)
add_library(hft::core ALIAS hft_core)

# PUBLIC: we need the headers to build hft_core, and anything that links
# hft_core needs them too.
target_include_directories(hft_core PUBLIC ${PROJECT_SOURCE_DIR}/include)
target_compile_features(hft_core PUBLIC cxx_std_20)
# Threads::Threads: std::thread / pthread_setaffinity_np. On older glibc
# this adds -pthread; on newer ones it is part of libc and costs nothing.
find_package(Threads REQUIRED)
target_link_libraries(hft_core PUBLIC Threads::Threads PRIVATE hft::warnings)
