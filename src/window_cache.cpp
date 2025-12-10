#include "geoslice/window_cache.hpp"
#include <cstring>

namespace geoslice {

WindowCache::WindowCache(size_t max_bytes) : max_bytes_(max_bytes) {}

uint64_t WindowCache::make_key(int x, int y, int width, int height) const {
    return (static_cast<uint64_t>(x) << 48) |
           (static_cast<uint64_t>(y) << 32) |
           (static_cast<uint64_t>(width) << 16) |
           static_cast<uint64_t>(height);
}

const uint8_t* WindowCache::get(int x, int y, int width, int height) {
    std::lock_guard<std::mutex> lock(mutex_);
    uint64_t key = make_key(x, y, width, height);

    auto it = cache_map_.find(key);
    if (it == cache_map_.end()) {
        misses_++;
        return nullptr;
    }

    hits_++;
    // Move to front (most recently used)
    lru_list_.splice(lru_list_.begin(), lru_list_, it->second);
    return it->second->second.data.data();
}

void WindowCache::evict_if_needed(size_t needed) {
    while (current_bytes_ + needed > max_bytes_ && !lru_list_.empty()) {
        auto& back = lru_list_.back();
        current_bytes_ -= back.second.data.size();
        cache_map_.erase(back.first);
        lru_list_.pop_back();
    }
}

void WindowCache::put(int x, int y, int width, int height, const uint8_t* data, size_t size) {
    std::lock_guard<std::mutex> lock(mutex_);
    uint64_t key = make_key(x, y, width, height);

    // Already cached?
    auto it = cache_map_.find(key);
    if (it != cache_map_.end()) {
        lru_list_.splice(lru_list_.begin(), lru_list_, it->second);
        return;
    }

    // Make room
    evict_if_needed(size);

    // Insert at front
    CachedWindow win{x, y, width, height, std::vector<uint8_t>(data, data + size)};
    lru_list_.emplace_front(key, std::move(win));
    cache_map_[key] = lru_list_.begin();
    current_bytes_ += size;
}

void WindowCache::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    lru_list_.clear();
    cache_map_.clear();
    current_bytes_ = 0;
}

} // namespace geoslice
