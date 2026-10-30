#include "hft/book/order_table.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <unordered_map>
#include <vector>

namespace {

using hft::OrderRef;
using hft::Side;
using hft::book::OrderEntry;
using hft::book::OrderTable;
using Result = OrderTable::InsertResult;

OrderEntry entry(OrderRef ref, hft::Qty shares = 100) {
  return OrderEntry{.ref = ref, .price = 1'000'000, .shares = shares, .locate = 1, .side = Side::Buy};
}

// Keys whose home slot is `slot`, found by brute force. Lets a test build a
// collision chain on purpose.
std::vector<OrderRef> keys_with_home(const OrderTable& t, std::size_t slot, std::size_t count) {
  std::vector<OrderRef> keys;
  for (OrderRef k = 1; keys.size() < count; ++k) {
    if (t.home(k) == slot) keys.push_back(k);
  }
  return keys;
}

TEST(OrderTable, SizesToPowerOfTwoAtLeastTwiceMax) {
  EXPECT_EQ(OrderTable(100).slot_count(), 256u);
  EXPECT_EQ(OrderTable(128).slot_count(), 256u);
  EXPECT_EQ(OrderTable(1).slot_count(), 16u);  // minimum
}

TEST(OrderTable, InsertFindErase) {
  OrderTable t(64);
  EXPECT_EQ(t.find(5), nullptr);
  EXPECT_EQ(t.insert(entry(5, 300)), Result::Inserted);
  ASSERT_NE(t.find(5), nullptr);
  EXPECT_EQ(t.find(5)->shares, 300u);
  EXPECT_EQ(t.size(), 1u);
  t.erase(t.find(5));
  EXPECT_EQ(t.find(5), nullptr);
  EXPECT_EQ(t.size(), 0u);
}

TEST(OrderTable, FindReturnsMutableEntry) {
  OrderTable t(64);
  t.insert(entry(5, 300));
  t.find(5)->shares = 10;
  EXPECT_EQ(t.find(5)->shares, 10u);
}

TEST(OrderTable, RejectsDuplicateEvenWhenFull) {
  OrderTable t(2);
  EXPECT_EQ(t.insert(entry(1)), Result::Inserted);
  EXPECT_EQ(t.insert(entry(2)), Result::Inserted);
  EXPECT_EQ(t.insert(entry(1)), Result::Duplicate);
  EXPECT_EQ(t.insert(entry(3)), Result::Full);
  EXPECT_EQ(t.size(), 2u);
}

// The core backward-shift case: erase the head of a collision chain. The
// entries behind it must shift back, or find() would stop at the gap.
TEST(OrderTable, EraseHeadOfCollisionChainKeepsOthersFindable) {
  OrderTable t(8);  // 16 slots
  const auto keys = keys_with_home(t, 3, 4);
  for (auto k : keys) ASSERT_EQ(t.insert(entry(k)), Result::Inserted);

  t.erase(t.find(keys[0]));
  for (std::size_t i = 1; i < keys.size(); ++i) {
    EXPECT_NE(t.find(keys[i]), nullptr) << "lost key " << keys[i];
  }
  EXPECT_EQ(t.find(keys[0]), nullptr);
}

TEST(OrderTable, EraseDoesNotMoveKeysBeforeTheirHome) {
  // Slot 3 holds a key whose home is 3; slots 4 and 5 hold keys whose home
  // is 4. Erasing slot 3 must leave the others where they are: moving b[0]
  // back into slot 3 would put it before its home, and find(b[0]), which
  // starts at slot 4, would never see it.
  OrderTable t(8);  // 16 slots
  const auto a = keys_with_home(t, 3, 1);
  const auto b = keys_with_home(t, 4, 2);
  t.insert(entry(a[0]));
  for (auto k : b) t.insert(entry(k));

  t.erase(t.find(a[0]));
  for (auto k : b) EXPECT_NE(t.find(k), nullptr) << "lost key " << k;
  t.erase(t.find(b[0]));
  EXPECT_NE(t.find(b[1]), nullptr);
}

TEST(OrderTable, EraseShiftsAcrossTwoChains) {
  // Homes 3, 3, then 4, 4: the second chain is pushed to slots 5 and 6.
  // Erasing slot 3 must pull every one of them back by one.
  OrderTable t(8);
  const auto a = keys_with_home(t, 3, 2);
  const auto b = keys_with_home(t, 4, 2);
  for (auto k : a) t.insert(entry(k));
  for (auto k : b) t.insert(entry(k));

  t.erase(t.find(a[0]));
  for (auto k : {a[1], b[0], b[1]}) EXPECT_NE(t.find(k), nullptr) << "lost key " << k;
}

TEST(OrderTable, ChainWrapsAroundTheEnd) {
  OrderTable t(8);  // 16 slots
  const auto keys = keys_with_home(t, 15, 4);  // slots 15, 0, 1, 2
  for (auto k : keys) ASSERT_EQ(t.insert(entry(k)), Result::Inserted);
  for (auto k : keys) EXPECT_NE(t.find(k), nullptr);
  t.erase(t.find(keys[1]));
  EXPECT_EQ(t.find(keys[1]), nullptr);
  for (auto k : {keys[0], keys[2], keys[3]}) EXPECT_NE(t.find(k), nullptr) << "lost key " << k;
}

// Randomised differential test: a million mixed operations, checked
// against std::unordered_map after each one.
TEST(OrderTable, MatchesUnorderedMapUnderRandomOperations) {
  OrderTable t(512);
  std::unordered_map<OrderRef, hft::Qty> ref;
  std::uint64_t rng = 12345;
  auto next = [&rng] {
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng;
  };

  for (int i = 0; i < 1'000'000; ++i) {
    const OrderRef key = 1 + next() % 2048;  // small key space: many collisions and repeats
    const auto it = ref.find(key);
    OrderEntry* e = t.find(key);
    ASSERT_EQ(e != nullptr, it != ref.end()) << "op " << i << " key " << key;
    if (it != ref.end()) {
      ASSERT_EQ(e->shares, it->second);
      t.erase(e);
      ref.erase(it);
    } else if (ref.size() < 512) {
      const auto shares = static_cast<hft::Qty>(next() % 1000);
      ASSERT_EQ(t.insert(entry(key, shares)), Result::Inserted);
      ref.emplace(key, shares);
    }
    ASSERT_EQ(t.size(), ref.size());
  }
  for (const auto& [k, shares] : ref) {
    ASSERT_NE(t.find(k), nullptr);
    EXPECT_EQ(t.find(k)->shares, shares);
  }
}

}  // namespace
