#pragma once

#include <cstdint>
#include <vector>
#include <unordered_map>
#include <list>
#include <mutex>
#include <memory>

namespace geoslice {

struct CachedWindow {
    int x, y, width, height;
    std::vector<uint8_t> data;
};

class WindowCache {
public:
    explicit WindowCache(size_t max_bytes = 256 * 1024 * 1024); // 256MB default

    const uint8_t* get(int x, int y, int width, int height);
    void put(int x, int y, int width, int height, const uint8_t* data, size_t size);
    void clear();

    size_t size() const { return current_bytes_; }
    size_t capacity() const { return max_bytes_; }
    size_t hits() const { return hits_; }
    size_t misses() const { return misses_; }

private:
    uint64_t make_key(int x, int y, int width, int height) const;
    void evict_if_needed(size_t needed);

    size_t max_bytes_;
    size_t current_bytes_ = 0;
    size_t hits_ = 0;
    size_t misses_ = 0;

    std::list<std::pair<uint64_t, CachedWindow>> lru_list_;
    std::unordered_map<uint64_t, decltype(lru_list_)::iterator> cache_map_;
    mutable std::mutex mutex_;
};

} // namespace geoslice
