#include "hft/common/mapped_file.hpp"

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <system_error>
#include <utility>

namespace hft {

namespace {

[[noreturn]] void throw_errno(const std::string& what) {
  throw std::system_error(errno, std::generic_category(), what);
}

}  // namespace

MappedFile::MappedFile(const std::string& path) {
  // O_CLOEXEC: don't leak the descriptor into any child process we exec.
  const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) throw_errno("open " + path);

  struct stat st {};
  if (::fstat(fd, &st) != 0) {
    const int err = errno;
    ::close(fd);
    errno = err;
    throw_errno("fstat " + path);
  }
  size_ = static_cast<std::size_t>(st.st_size);

  // mmap() of length 0 fails with EINVAL, so an empty file is simply an
  // empty span.
  if (size_ > 0) {
    // MAP_PRIVATE + PROT_READ: we only read. The pages are shared with the
    // kernel's page cache, so a second run over the same file costs no I/O.
    void* p = ::mmap(nullptr, size_, PROT_READ, MAP_PRIVATE, fd, 0);
    if (p == MAP_FAILED) {
      const int err = errno;
      ::close(fd);
      errno = err;
      throw_errno("mmap " + path);
    }
    data_ = p;
    // Tell the kernel we'll read front to back: it reads ahead more
    // aggressively and drops pages behind us sooner.
    ::madvise(data_, size_, MADV_SEQUENTIAL);
  }

  // The mapping keeps the file alive; the descriptor is no longer needed.
  ::close(fd);
}

MappedFile::~MappedFile() { release(); }

// std::exchange(x, v) sets x to v and returns the old value: take the other
// object's mapping and leave it empty, so its destructor does nothing.
MappedFile::MappedFile(MappedFile&& other) noexcept
    : data_(std::exchange(other.data_, nullptr)), size_(std::exchange(other.size_, 0)) {}

MappedFile& MappedFile::operator=(MappedFile&& other) noexcept {
  if (this != &other) {
    release();  // drop our current mapping first, or it leaks
    data_ = std::exchange(other.data_, nullptr);
    size_ = std::exchange(other.size_, 0);
  }
  return *this;
}

void MappedFile::release() noexcept {
  if (data_ != nullptr) {
    ::munmap(data_, size_);
    data_ = nullptr;
    size_ = 0;
  }
}

}  // namespace hft
