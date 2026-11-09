# Sanitizer builds.
#
# The flags are added globally (add_compile_options / add_link_options) rather
# than per target, so the third-party code we build from source is instrumented
# too. TSan needs this: code it can't see doesn't report its synchronisation,
# and TSan then reports races that aren't there.
#
# ASan and TSan can't be combined: each one reserves its own huge "shadow"
# region of the address space, and the two layouts collide.

if(HFT_SANITIZER STREQUAL "none")
  return()
elseif(HFT_SANITIZER STREQUAL "asan")
  # AddressSanitizer: out-of-bounds, use-after-free, double free, leaks.
  # UndefinedBehaviorSanitizer is cheap and compatible, so it rides along.
  set(_hft_san_flags -fsanitize=address,undefined)
elseif(HFT_SANITIZER STREQUAL "tsan")
  # ThreadSanitizer: data races and lock-order inversions.
  set(_hft_san_flags -fsanitize=thread)
else()
  message(FATAL_ERROR "HFT_SANITIZER must be none, asan or tsan (got '${HFT_SANITIZER}')")
endif()

# -fno-sanitize-recover=all: UBSan prints a report and carries on by default,
#   so a test with UB would still pass. Make every report fatal.
# -fno-omit-frame-pointer: readable stack traces in sanitizer reports.
add_compile_options(${_hft_san_flags} -fno-sanitize-recover=all -fno-omit-frame-pointer)
add_link_options(${_hft_san_flags})

message(STATUS "Sanitizer: ${HFT_SANITIZER} (${_hft_san_flags})")
