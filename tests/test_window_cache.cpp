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

    const uint8_t* result = cache.get(0, 0, 10, 10);
    ASSERT_NE(result, nullptr);
    EXPECT_EQ(result[0], test_data[0]);
    EXPECT_EQ(result[100], test_data[100]);
}

TEST_F(WindowCacheTest, MissReturnsNull) {
    geoslice::WindowCache cache(4096);

    const uint8_t* result = cache.get(0, 0, 10, 10);
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
