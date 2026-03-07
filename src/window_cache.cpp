#include "geoslice/window_cache.hpp"
#include <cstring>

namespace geoslice {

WindowCache::WindowCache(size_t max_bytes) : max_bytes_(max_bytes) {}

uint64_t WindowCache::make_key(int x, int y, int width, int height) const {
    // FNV-1a hash — handles full int range without truncation
    uint64_t h = 14695981039346656037ULL;
    constexpr uint64_t fnv_prime = 1099511628211ULL;
    auto mix = [&h, fnv_prime](int v) {
        auto bytes = static_cast<uint32_t>(v);
        for (int i = 0; i < 4; ++i) {
            h ^= (bytes >> (i * 8)) & 0xFF;
            h *= fnv_prime;
        }
    };
    mix(x);
    mix(y);
    mix(width);
    mix(height);
    return h;
}

std::shared_ptr<const CachedWindow> WindowCache::get(int x, int y, int width, int height) {
    std::lock_guard<std::mutex> lock(mutex_);
    uint64_t key = make_key(x, y, width, height);

    auto it = cache_map_.find(key);
    if (it == cache_map_.end()) {
        misses_++;
        return nullptr;
    }

    // Verify coordinates match (hash collision detection)
    auto& entry = it->second->second;
    if (entry->x != x || entry->y != y || entry->width != width || entry->height != height) {
        misses_++;
        return nullptr;
    }

    hits_++;
    lru_list_.splice(lru_list_.begin(), lru_list_, it->second);
    return entry;
}

void WindowCache::evict_if_needed(size_t needed) {
    while (current_bytes_ + needed > max_bytes_ && !lru_list_.empty()) {
        auto& back = lru_list_.back();
        current_bytes_ -= back.second->data.size();
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
        auto& entry = it->second->second;
        if (entry->x == x && entry->y == y && entry->width == width && entry->height == height) {
            lru_list_.splice(lru_list_.begin(), lru_list_, it->second);
            return;
        }
        // Hash collision with different coordinates — evict old entry
        current_bytes_ -= entry->data.size();
        lru_list_.erase(it->second);
        cache_map_.erase(it);
    }

    // Make room
    evict_if_needed(size);

    // Insert at front
    auto win = std::make_shared<CachedWindow>(
        CachedWindow{x, y, width, height, std::vector<uint8_t>(data, data + size)});
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
