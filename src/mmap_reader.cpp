#include "geoslice/mmap_reader.hpp"

#include <fstream>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cstring>

// Minimal JSON parsing (no deps)
namespace {
std::string extract_string(const std::string& json, const std::string& key) {
    auto pos = json.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos);
    auto start = json.find('"', pos) + 1;
    auto end = json.find('"', start);
    return json.substr(start, end - start);
}

int extract_int(const std::string& json, const std::string& key) {
    auto pos = json.find("\"" + key + "\"");
    if (pos == std::string::npos) return 0;
    pos = json.find(':', pos) + 1;
    while (json[pos] == ' ') pos++;
    return std::stoi(json.substr(pos));
}

std::array<double, 6> extract_transform(const std::string& json) {
    std::array<double, 6> result{};
    auto pos = json.find("\"transform\"");
    if (pos == std::string::npos) return result;
    pos = json.find('[', pos);
    for (int i = 0; i < 6; i++) {
        pos++;
        while (json[pos] == ' ' || json[pos] == '\n') pos++;
        result[i] = std::stod(json.substr(pos));
        pos = json.find_first_of(",]", pos);
    }
    return result;
}
}

namespace geoslice {

size_t GeoMetadata::pixel_size() const {
    if (dtype == "uint8") return 1;
    if (dtype == "uint16" || dtype == "int16") return 2;
    if (dtype == "uint32" || dtype == "int32" || dtype == "float32") return 4;
    if (dtype == "float64") return 8;
    return 1;
}

size_t GeoMetadata::total_bytes() const {
    return static_cast<size_t>(count) * height * width * pixel_size();
}

MMapReader::MMapReader(const std::string& base_path) {
    // Load JSON metadata
    std::ifstream json_file(base_path + ".json");
    if (!json_file) throw std::runtime_error("Cannot open " + base_path + ".json");

    std::string json((std::istreambuf_iterator<char>(json_file)), std::istreambuf_iterator<char>());

    meta_.dtype = extract_string(json, "dtype");
    meta_.count = extract_int(json, "count");
    meta_.height = extract_int(json, "height");
    meta_.width = extract_int(json, "width");
    meta_.transform = extract_transform(json);
    meta_.crs = extract_string(json, "crs");

    // Memory map binary file
    std::string bin_path = base_path + ".bin";
    fd_ = open(bin_path.c_str(), O_RDONLY);
    if (fd_ < 0) throw std::runtime_error("Cannot open " + bin_path);

    struct stat st;
    fstat(fd_, &st);
    mapped_size_ = st.st_size;

    mapped_data_ = mmap(nullptr, mapped_size_, PROT_READ, MAP_PRIVATE, fd_, 0);
    if (mapped_data_ == MAP_FAILED) {
        close(fd_);
        throw std::runtime_error("mmap failed");
    }

    // Advise kernel for random access
    madvise(mapped_data_, mapped_size_, MADV_RANDOM);
}

MMapReader::~MMapReader() {
    if (mapped_data_ && mapped_data_ != MAP_FAILED) {
        munmap(mapped_data_, mapped_size_);
    }
    if (fd_ >= 0) close(fd_);
}

MMapReader::MMapReader(MMapReader&& other) noexcept
    : meta_(std::move(other.meta_))
    , mapped_data_(other.mapped_data_)
    , mapped_size_(other.mapped_size_)
    , fd_(other.fd_) {
    other.mapped_data_ = nullptr;
    other.fd_ = -1;
}

MMapReader& MMapReader::operator=(MMapReader&& other) noexcept {
    if (this != &other) {
        if (mapped_data_ && mapped_data_ != MAP_FAILED) munmap(mapped_data_, mapped_size_);
        if (fd_ >= 0) close(fd_);

        meta_ = std::move(other.meta_);
        mapped_data_ = other.mapped_data_;
        mapped_size_ = other.mapped_size_;
        fd_ = other.fd_;

        other.mapped_data_ = nullptr;
        other.fd_ = -1;
    }
    return *this;
}

bool MMapReader::is_valid_window(int x, int y, int width, int height) const {
    return x >= 0 && y >= 0 &&
           x + width <= meta_.width &&
           y + height <= meta_.height &&
           width > 0 && height > 0;
}

WindowView MMapReader::get_window(int x, int y, int width, int height) const {
    if (!is_valid_window(x, y, width, height)) {
        throw std::out_of_range("Window out of bounds");
    }

    size_t psize = meta_.pixel_size();
    size_t band_stride = static_cast<size_t>(meta_.height) * meta_.width * psize;
    size_t row_stride = static_cast<size_t>(meta_.width) * psize;

    const uint8_t* base = static_cast<const uint8_t*>(mapped_data_);
    const uint8_t* window_start = base + y * row_stride + x * psize;

    return WindowView{
        window_start,
        meta_.count,
        height,
        width,
        band_stride,
        row_stride,
        psize
    };
}

} // namespace geoslice
