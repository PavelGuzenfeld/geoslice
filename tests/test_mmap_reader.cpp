#include <gtest/gtest.h>
#include "geoslice/mmap_reader.hpp"
#include <fstream>
#include <cstdio>

class MMapReaderTest : public ::testing::Test {
protected:
    std::string test_base = "/tmp/test_geoslice";

    void SetUp() override {
        // Create test JSON
        std::ofstream json(test_base + ".json");
        json << R"({
            "dtype": "uint8",
            "count": 3,
            "height": 100,
            "width": 200,
            "transform": [1.0, 0.0, 0.0, 0.0, -1.0, 100.0],
            "crs": "EPSG:32636"
        })";
        json.close();

        // Create test binary (3 bands * 100 rows * 200 cols)
        std::ofstream bin(test_base + ".bin", std::ios::binary);
        std::vector<uint8_t> data(3 * 100 * 200);
        for (size_t i = 0; i < data.size(); i++) {
            data[i] = static_cast<uint8_t>(i % 256);
        }
        bin.write(reinterpret_cast<char*>(data.data()), data.size());
        bin.close();
    }

    void TearDown() override {
        std::remove((test_base + ".json").c_str());
        std::remove((test_base + ".bin").c_str());
    }
};

TEST_F(MMapReaderTest, LoadsMetadata) {
    geoslice::MMapReader reader(test_base);

    EXPECT_EQ(reader.width(), 200);
    EXPECT_EQ(reader.height(), 100);
    EXPECT_EQ(reader.bands(), 3);
    EXPECT_EQ(reader.metadata().dtype, "uint8");
    EXPECT_EQ(reader.metadata().crs, "EPSG:32636");
}

TEST_F(MMapReaderTest, ValidWindowCheck) {
    geoslice::MMapReader reader(test_base);

    EXPECT_TRUE(reader.is_valid_window(0, 0, 10, 10));
    EXPECT_TRUE(reader.is_valid_window(190, 90, 10, 10));
    EXPECT_FALSE(reader.is_valid_window(-1, 0, 10, 10));
    EXPECT_FALSE(reader.is_valid_window(0, 0, 201, 10));
    EXPECT_FALSE(reader.is_valid_window(195, 0, 10, 10));
}

TEST_F(MMapReaderTest, GetWindowReturnsView) {
    geoslice::MMapReader reader(test_base);

    auto view = reader.get_window(0, 0, 10, 10);

    EXPECT_EQ(view.bands, 3);
    EXPECT_EQ(view.width, 10);
    EXPECT_EQ(view.height, 10);
    EXPECT_NE(view.data, nullptr);
}

TEST_F(MMapReaderTest, WindowDataCorrect) {
    geoslice::MMapReader reader(test_base);

    auto view = reader.get_window(0, 0, 10, 10);

    // First pixel of first band should be 0
    EXPECT_EQ(view.at<uint8_t>(0, 0, 0), 0);
    // Second pixel should be 1
    EXPECT_EQ(view.at<uint8_t>(0, 0, 1), 1);
}

TEST_F(MMapReaderTest, ThrowsOnInvalidWindow) {
    geoslice::MMapReader reader(test_base);

    EXPECT_THROW(reader.get_window(-1, 0, 10, 10), std::out_of_range);
    EXPECT_THROW(reader.get_window(195, 0, 10, 10), std::out_of_range);
}

TEST_F(MMapReaderTest, MoveConstruction) {
    geoslice::MMapReader reader1(test_base);
    geoslice::MMapReader reader2(std::move(reader1));

    EXPECT_EQ(reader2.width(), 200);
    auto view = reader2.get_window(0, 0, 10, 10);
    EXPECT_NE(view.data, nullptr);
}
