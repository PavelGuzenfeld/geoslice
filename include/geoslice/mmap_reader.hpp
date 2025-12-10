#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <array>
#include <memory>
#include <stdexcept>

namespace geoslice {

struct GeoMetadata {
    std::string dtype;
    int count;      // bands
    int height;
    int width;
    std::array<double, 6> transform;
    std::string crs;

    size_t pixel_size() const;
    size_t total_bytes() const;
};

struct WindowView {
    const uint8_t* data;
    int bands;
    int height;
    int width;
    size_t stride_band;
    size_t stride_row;
    size_t pixel_size;

    template<typename T>
    const T* band(int b) const {
        return reinterpret_cast<const T*>(data + b * stride_band);
    }

    template<typename T>
    T at(int b, int y, int x) const {
        return *reinterpret_cast<const T*>(data + b * stride_band + y * stride_row + x * pixel_size);
    }
};

class MMapReader {
public:
    explicit MMapReader(const std::string& base_path);
    ~MMapReader();

    MMapReader(const MMapReader&) = delete;
    MMapReader& operator=(const MMapReader&) = delete;
    MMapReader(MMapReader&&) noexcept;
    MMapReader& operator=(MMapReader&&) noexcept;

    WindowView get_window(int x, int y, int width, int height) const;
    bool is_valid_window(int x, int y, int width, int height) const;

    const GeoMetadata& metadata() const { return meta_; }
    int width() const { return meta_.width; }
    int height() const { return meta_.height; }
    int bands() const { return meta_.count; }

private:
    GeoMetadata meta_;
    void* mapped_data_ = nullptr;
    size_t mapped_size_ = 0;
    int fd_ = -1;
};

} // namespace geoslice
