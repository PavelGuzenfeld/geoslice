#include <gtest/gtest.h>
#include "geoslice/window_cache.hpp"

class WindowCacheTest : public ::testing::Test {
protected:
    std::vector<uint8_t> test_data;

    void SetUp() override {
        test_data.resize(1024);
        for (size_t i = 0; i < test_data.size(); i++) {
            test_data[i] = static_cast<uint8_t>(i % 256);
        }
    }
};

TEST_F(WindowCacheTest, InitialState) {
    geoslice::WindowCache cache(1024);

    EXPECT_EQ(cache.size(), 0u);
    EXPECT_EQ(cache.capacity(), 1024u);
    EXPECT_EQ(cache.hits(), 0u);
    EXPECT_EQ(cache.misses(), 0u);
}

TEST_F(WindowCacheTest, PutAndGet) {
    geoslice::WindowCache cache(4096);

    cache.put(0, 0, 10, 10, test_data.data(), test_data.size());

    auto result = cache.get(0, 0, 10, 10);
    ASSERT_NE(result, nullptr);
    EXPECT_EQ(result->data[0], test_data[0]);
    EXPECT_EQ(result->data[100], test_data[100]);
}

TEST_F(WindowCacheTest, MissReturnsNull) {
    geoslice::WindowCache cache(4096);

    auto result = cache.get(0, 0, 10, 10);
    EXPECT_EQ(result, nullptr);
    EXPECT_EQ(cache.misses(), 1u);
}

TEST_F(WindowCacheTest, HitCountsCorrectly) {
    geoslice::WindowCache cache(4096);

    cache.put(0, 0, 10, 10, test_data.data(), test_data.size());

    cache.get(0, 0, 10, 10);
    cache.get(0, 0, 10, 10);
    cache.get(0, 0, 10, 10);

    EXPECT_EQ(cache.hits(), 3u);
}

TEST_F(WindowCacheTest, EvictsOldEntries) {
    // Cache that can hold ~2 entries
    geoslice::WindowCache cache(2048);

    // Insert 3 entries
    cache.put(0, 0, 10, 10, test_data.data(), 1024);
    cache.put(1, 1, 10, 10, test_data.data(), 1024);
    cache.put(2, 2, 10, 10, test_data.data(), 1024);

    // First entry should be evicted
    EXPECT_EQ(cache.get(0, 0, 10, 10), nullptr);
    EXPECT_NE(cache.get(2, 2, 10, 10), nullptr);
}

TEST_F(WindowCacheTest, LRUOrder) {
    geoslice::WindowCache cache(2048);

    cache.put(0, 0, 10, 10, test_data.data(), 1024);
    cache.put(1, 1, 10, 10, test_data.data(), 1024);

    // Access first entry to make it recently used
    cache.get(0, 0, 10, 10);

    // Insert third entry
    cache.put(2, 2, 10, 10, test_data.data(), 1024);

    // Second entry (least recently used) should be evicted
    EXPECT_NE(cache.get(0, 0, 10, 10), nullptr);
    EXPECT_EQ(cache.get(1, 1, 10, 10), nullptr);
}

TEST_F(WindowCacheTest, Clear) {
    geoslice::WindowCache cache(4096);

    cache.put(0, 0, 10, 10, test_data.data(), test_data.size());
    cache.clear();

    EXPECT_EQ(cache.size(), 0u);
    EXPECT_EQ(cache.get(0, 0, 10, 10), nullptr);
}

TEST_F(WindowCacheTest, DuplicatePutNoOp) {
    geoslice::WindowCache cache(4096);

    cache.put(0, 0, 10, 10, test_data.data(), 1024);
    size_t size_after_first = cache.size();

    cache.put(0, 0, 10, 10, test_data.data(), 1024);

    // Size should not change
    EXPECT_EQ(cache.size(), size_after_first);
}

TEST_F(WindowCacheTest, SharedPtrKeepsDataAliveAfterEviction) {
    geoslice::WindowCache cache(1024);

    cache.put(0, 0, 10, 10, test_data.data(), 1024);

    // Get a shared_ptr to the cached data
    auto held = cache.get(0, 0, 10, 10);
    ASSERT_NE(held, nullptr);

    // Evict by inserting a new entry
    cache.put(1, 1, 10, 10, test_data.data(), 1024);

    // Original entry is evicted from cache
    EXPECT_EQ(cache.get(0, 0, 10, 10), nullptr);

    // But our held shared_ptr still has valid data
    EXPECT_EQ(held->data[0], test_data[0]);
    EXPECT_EQ(held->data[100], test_data[100]);
}

TEST_F(WindowCacheTest, LargeCoordinatesWork) {
    geoslice::WindowCache cache(4096);

    // Coordinates > 65535 would collide with old bit-packing approach
    cache.put(100000, 200000, 512, 512, test_data.data(), test_data.size());

    auto result = cache.get(100000, 200000, 512, 512);
    ASSERT_NE(result, nullptr);
    EXPECT_EQ(result->data[0], test_data[0]);

    // Different large coordinates should not collide
    auto miss = cache.get(100001, 200000, 512, 512);
    EXPECT_EQ(miss, nullptr);
}
