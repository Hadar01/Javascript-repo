#include "hft/common/mapped_file.hpp"

#include <gtest/gtest.h>

#include <cstdio>
#include <string>
#include <system_error>
#include <utility>

namespace {

using hft::MappedFile;

std::string write_temp(const std::string& name, const std::string& contents) {
  const std::string path = ::testing::TempDir() + name;
  std::FILE* f = std::fopen(path.c_str(), "wb");
  EXPECT_NE(f, nullptr);
  std::fwrite(contents.data(), 1, contents.size(), f);
  std::fclose(f);
  return path;
}

std::string as_string(const MappedFile& m) {
  const auto b = m.bytes();
  return {reinterpret_cast<const char*>(b.data()), b.size()};
}

TEST(MappedFile, MapsContents) {
  const MappedFile m(write_temp("mapped_file_contents", "hello itch"));
  EXPECT_EQ(m.size(), 10u);
  EXPECT_EQ(as_string(m), "hello itch");
}

TEST(MappedFile, EmptyFileGivesEmptySpan) {
  const MappedFile m(write_temp("mapped_file_empty", ""));
  EXPECT_EQ(m.size(), 0u);
  EXPECT_TRUE(m.bytes().empty());
}

TEST(MappedFile, MissingFileThrows) {
  EXPECT_THROW(MappedFile("/nonexistent/definitely/not/here"), std::system_error);
}

TEST(MappedFile, MoveTransfersOwnership) {
  MappedFile a(write_temp("mapped_file_move", "abc"));
  MappedFile b(std::move(a));
  EXPECT_EQ(as_string(b), "abc");
  // Reading a moved-from object is normally a bug. Here our own move
  // constructor defines the moved-from state (empty), so we check it.
  EXPECT_EQ(a.size(), 0u);
  EXPECT_TRUE(a.bytes().empty());

  MappedFile c(write_temp("mapped_file_move2", "defg"));
  c = std::move(b);  // c must unmap "defg" first, or that mapping leaks
  EXPECT_EQ(as_string(c), "abc");
  EXPECT_EQ(b.size(), 0u);
}

}  // namespace
