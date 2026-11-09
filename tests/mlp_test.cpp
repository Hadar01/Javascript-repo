#include "hft/model/mlp.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "hft/strategy/model_strategy.hpp"

namespace {

using hft::model::Mlp;
// An alias, because Mlp<2, 2, 1> inside EXPECT_THROW(...) would be split at
// its commas: the preprocessor knows nothing about templates.
using Tiny = Mlp<2, 2, 1>;

const std::string kDataDir = HFT_TEST_DATA_DIR;

// Writes an HFTMLP01 file, so tests can build models with known weights.
void write_model(const std::string& path, std::uint32_t in, std::uint32_t h1, std::uint32_t h2,
                 const std::vector<float>& values, const char* magic = "HFTMLP01") {
  std::ofstream f(path, std::ios::binary);
  f.write(magic, 8);
  const std::uint32_t dims[3] = {in, h1, h2};
  f.write(reinterpret_cast<const char*>(dims), sizeof dims);
  f.write(reinterpret_cast<const char*>(values.data()), static_cast<std::streamsize>(values.size() * sizeof(float)));
}

// Number of floats in a model of these sizes.
std::size_t model_floats(std::size_t in, std::size_t h1, std::size_t h2) {
  return 2 * in + in * h1 + h1 + h1 * h2 + h2 + h2 + 1;
}

TEST(Mlp, ComputesTheExpectedLogit) {
  // in=2, h1=2, h2=1, worked out by hand:
  //   z  = (x - mean) * inv_std = ((3-1)*0.5, (4-0)*1) = (1, 4)
  //   h1 = relu(b1 + w1^T z), w1 = [[1, -1], [2, 0]] (input-major), b1 = (0, 1)
  //      = relu(0 + 1*1 + 2*4, 1 + -1*1 + 0*4) = relu(9, 0) = (9, 0)
  //   h2 = relu(b2 + w2^T h1), w2 = [[0.5], [3]], b2 = (-1) -> relu(-1 + 4.5 + 0) = 3.5
  //   logit = b3 + w3 * h2 = 0.25 + 2 * 3.5 = 7.25
  const std::string path = ::testing::TempDir() + "tiny.mlp";
  write_model(path, 2, 2, 1,
              {1, 0,           // mean
               0.5f, 1,        // inv_std
               1, -1, 2, 0,    // w1 [in][h1]
               0, 1,           // b1
               0.5f, 3,        // w2 [h1][h2]
               -1,             // b2
               2,              // w3
               0.25f});        // b3
  const auto m = Tiny::load(path);
  EXPECT_FLOAT_EQ(m.logit({3, 4}), 7.25f);
  EXPECT_NEAR(m.probability({3, 4}), 1.0 / (1.0 + std::exp(-7.25)), 1e-6);
}

TEST(Mlp, RejectsBadFiles) {
  const std::string dir = ::testing::TempDir();
  const std::vector<float> good(model_floats(2, 2, 1), 0.0f);

  EXPECT_THROW(Tiny::load(dir + "does-not-exist.mlp"), std::runtime_error);

  write_model(dir + "magic.mlp", 2, 2, 1, good, "NOTAMLP!");
  EXPECT_THROW(Tiny::load(dir + "magic.mlp"), std::runtime_error);

  write_model(dir + "dims.mlp", 3, 2, 1, std::vector<float>(model_floats(3, 2, 1), 0.0f));
  EXPECT_THROW(Tiny::load(dir + "dims.mlp"), std::runtime_error);  // built for 3 inputs

  write_model(dir + "short.mlp", 2, 2, 1, std::vector<float>(good.size() - 1, 0.0f));
  EXPECT_THROW(Tiny::load(dir + "short.mlp"), std::runtime_error);

  write_model(dir + "long.mlp", 2, 2, 1, std::vector<float>(good.size() + 1, 0.0f));
  EXPECT_THROW(Tiny::load(dir + "long.mlp"), std::runtime_error);

  write_model(dir + "ok.mlp", 2, 2, 1, good);
  EXPECT_NO_THROW(Tiny::load(dir + "ok.mlp"));
}

// Train/serve parity: python/train.py wrote 1,000 test inputs together with
// scikit-learn's predictions for them. The C++ model, loaded from the
// exported file, must reproduce them. This catches every export mistake: a
// transposed matrix, a missing standardisation, a wrong layer order.
TEST(Mlp, MatchesPythonOnTheGoldenFile) {
  const auto m = hft::strategy::DefaultModel::load(kDataDir + "/model.bin");
  std::ifstream f(kDataDir + "/golden.bin", std::ios::binary);
  ASSERT_TRUE(f) << "missing tests/data/golden.bin";
  char magic[8];
  std::uint32_t dims[2];
  f.read(magic, 8);
  f.read(reinterpret_cast<char*>(dims), sizeof dims);
  ASSERT_EQ(std::string(magic, 8), "HFTGLD01");
  ASSERT_EQ(dims[0], hft::features::kNumFeatures);
  const std::size_t n = dims[1];
  std::vector<hft::features::FeatureVector> x(n);
  std::vector<float> p(n);
  f.read(reinterpret_cast<char*>(x.data()), static_cast<std::streamsize>(n * sizeof(x[0])));
  f.read(reinterpret_cast<char*>(p.data()), static_cast<std::streamsize>(n * sizeof(float)));
  ASSERT_TRUE(f);

  double max_diff = 0;
  std::size_t disagreements = 0;
  for (std::size_t i = 0; i < n; ++i) {
    const float cpp = m.probability(x[i]);
    max_diff = std::max(max_diff, static_cast<double>(std::abs(cpp - p[i])));
    // The decision may only differ where Python itself sits on the fence.
    if ((cpp > 0.5f) != (p[i] > 0.5f) && std::abs(p[i] - 0.5f) > 1e-4f) ++disagreements;
  }
  // Python computes in double, C++ in float: expect agreement to ~1e-6.
  EXPECT_LT(max_diff, 1e-4) << "largest |C++ - Python| probability difference";
  EXPECT_EQ(disagreements, 0u);
  std::printf("[ golden   ] %zu rows, largest probability difference %.2e\n", n, max_diff);
}

}  // namespace
