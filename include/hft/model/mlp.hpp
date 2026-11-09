#pragma once

// A small multilayer perceptron for inference in nanoseconds.
//
//   x (In) -> standardise -> dense H1 + ReLU -> dense H2 + ReLU -> dense 1 -> logit
//
// The sizes are template parameters, so every loop has a constant trip
// count the compiler can unroll and vectorise. Weights are float: half the
// memory of double, and twice as many values per SIMD register. The whole
// model (~3.5 KB) fits in L1.
//
// The weights are stored TRANSPOSED (input-major), so a dense layer is
//   for each input i:  h[0..H) += w[i][0..H) * x[i]
// The inner loop is an element-wise multiply-add over H independent outputs.
// The compiler can vectorise that as written. The textbook form,
//   for each output j:  h[j] = sum over i of w[j][i] * x[i]
// is a reduction (a running sum), and vectorising it would change the order
// of floating-point additions. The compiler may not do that without
// -ffast-math, because float addition isn't associative.
//
// File format (little-endian, written by python/train.py):
//   "HFTMLP01"  u32 in  u32 h1  u32 h2
//   f32 mean[in]  f32 inv_std[in]
//   f32 w1[in][h1]  f32 b1[h1]
//   f32 w2[h1][h2]  f32 b2[h2]
//   f32 w3[h2]      f32 b3

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>

namespace hft::model {

template <std::size_t In, std::size_t H1, std::size_t H2>
class Mlp {
 public:
  using Input = std::array<float, In>;

  // Throws std::runtime_error if the file is missing, truncated, or built for
  // other dimensions. That is checked once at startup, never at inference.
  static Mlp load(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open model file " + path);
    char magic[8];
    std::uint32_t dims[3];
    f.read(magic, sizeof magic);
    f.read(reinterpret_cast<char*>(dims), sizeof dims);
    if (!f || std::memcmp(magic, "HFTMLP01", 8) != 0) throw std::runtime_error(path + ": not an HFTMLP01 model");
    if (dims[0] != In || dims[1] != H1 || dims[2] != H2) {
      throw std::runtime_error(path + ": model is " + std::to_string(dims[0]) + "-" + std::to_string(dims[1]) + "-" +
                               std::to_string(dims[2]) + ", this build expects " + std::to_string(In) + "-" +
                               std::to_string(H1) + "-" + std::to_string(H2));
    }
    Mlp m;
    auto read = [&](auto& arr) { f.read(reinterpret_cast<char*>(arr.data()), sizeof arr); };
    read(m.mean_);
    read(m.inv_std_);
    read(m.w1_);
    read(m.b1_);
    read(m.w2_);
    read(m.b2_);
    read(m.w3_);
    f.read(reinterpret_cast<char*>(&m.b3_), sizeof m.b3_);
    if (!f) throw std::runtime_error(path + ": truncated model file");
    if (f.peek() != std::char_traits<char>::eof()) throw std::runtime_error(path + ": trailing bytes after the model");
    return m;
  }

  // log(p / (1 - p)) for "the next mid move is up". The decision p > 0.5 is
  // exactly logit > 0, so a strategy compares logits and skips the exp.
  [[nodiscard]] float logit(const Input& x) const noexcept {
    alignas(64) std::array<float, In> z;
    for (std::size_t i = 0; i < In; ++i) z[i] = (x[i] - mean_[i]) * inv_std_[i];

    alignas(64) std::array<float, H1> h1 = b1_;
    for (std::size_t i = 0; i < In; ++i) {
      for (std::size_t j = 0; j < H1; ++j) h1[j] += w1_[i * H1 + j] * z[i];
    }
    for (auto& v : h1) v = v > 0.0f ? v : 0.0f;  // ReLU: compiles to a vector max, no branch

    alignas(64) std::array<float, H2> h2 = b2_;
    for (std::size_t i = 0; i < H1; ++i) {
      for (std::size_t j = 0; j < H2; ++j) h2[j] += w2_[i * H2 + j] * h1[i];
    }
    for (auto& v : h2) v = v > 0.0f ? v : 0.0f;

    // The last layer has one output, so it is a true dot product (a
    // reduction). With only H2 terms it is a handful of instructions anyway.
    float out = b3_;
    for (std::size_t j = 0; j < H2; ++j) out += w3_[j] * h2[j];
    return out;
  }

  [[nodiscard]] float probability(const Input& x) const noexcept { return 1.0f / (1.0f + std::exp(-logit(x))); }

 private:
  Mlp() = default;

  alignas(64) std::array<float, In> mean_{};
  alignas(64) std::array<float, In> inv_std_{};  // multiply instead of divide: ~4x cheaper per element
  alignas(64) std::array<float, In * H1> w1_{};  // [in][h1]
  alignas(64) std::array<float, H1> b1_{};
  alignas(64) std::array<float, H1 * H2> w2_{};  // [h1][h2]
  alignas(64) std::array<float, H2> b2_{};
  alignas(64) std::array<float, H2> w3_{};
  float b3_ = 0.0f;
};

}  // namespace hft::model
