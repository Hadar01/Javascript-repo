# Warning flags for our own code.
#
# They live on an INTERFACE library: it compiles nothing, it only carries usage
# requirements. Every target of ours links it, so the flags reach our code and
# never reach GoogleTest or Google Benchmark, whose warnings we can't fix.

add_library(hft_warnings INTERFACE)
add_library(hft::warnings ALIAS hft_warnings)

target_compile_options(hft_warnings INTERFACE
  -Wall
  -Wextra
  -Wpedantic            # reject compiler extensions (VLAs, zero-length arrays...)
  -Wshadow              # a local variable hides an outer one
  -Wconversion          # implicit narrowing, e.g. uint64_t -> uint32_t
  -Wsign-conversion     # implicit signed <-> unsigned, e.g. int -> size_t
  -Wold-style-cast      # (T)x hides what kind of cast it is; use static_cast etc.
  -Wdouble-promotion    # float silently widened to double (slower, and a sign of a typo)
)

if(HFT_WERROR)
  target_compile_options(hft_warnings INTERFACE -Werror)
endif()
