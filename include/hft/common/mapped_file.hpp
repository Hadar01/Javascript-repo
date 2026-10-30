#pragma once

// A read-only memory-mapped file.
//
// mmap() makes the file's bytes appear directly in our address space. The
// kernel loads pages on first touch and reads ahead for sequential access.
// Compared with read() into a buffer:
//   - no copy from the kernel's page cache into our own buffer
//   - no message ever straddles two read() chunks, so the parser sees one
//     contiguous span and needs no "partial message" handling
//
// The class owns the mapping (RAII): the destructor unmaps it. It is
// move-only. A copy would give two objects that both unmap the same memory,
// the mmap equivalent of a double free.

#include <cstddef>
#include <span>
#include <string>

namespace hft {

class MappedFile {
 public:
  // Throws std::system_error if the file can't be opened or mapped. This is
  // setup code, so an exception is the right tool here.
  explicit MappedFile(const std::string& path);
  ~MappedFile();

  MappedFile(const MappedFile&) = delete;
  MappedFile& operator=(const MappedFile&) = delete;
  MappedFile(MappedFile&& other) noexcept;
  MappedFile& operator=(MappedFile&& other) noexcept;

  [[nodiscard]] std::span<const std::byte> bytes() const noexcept {
    return {static_cast<const std::byte*>(data_), size_};
  }
  [[nodiscard]] std::size_t size() const noexcept { return size_; }

 private:
  void release() noexcept;

  void* data_ = nullptr;
  std::size_t size_ = 0;
};

}  // namespace hft
