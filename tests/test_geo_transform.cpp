#include <gtest/gtest.h>
#include "geoslice/geo_transform.hpp"
#include <cmath>

class GeoTransformTest : public ::testing::Test {
protected:
    std::array<double, 6> test_transform = {
        0.337810489610016,  // pixel_size_x
        0.0,
        668780.082,         // origin_x
        0.0,
        -0.40736344335616,  // pixel_size_y (negative)
        3481925.5373        // origin_y
    };
};

TEST_F(GeoTransformTest, PixelSizes) {
    geoslice::GeoTransform geo(test_transform, 36);

    EXPECT_NEAR(geo.pixel_size_x(), 0.337810489610016, 1e-10);
    EXPECT_NEAR(geo.pixel_size_y(), 0.40736344335616, 1e-10);
}

TEST_F(GeoTransformTest, LatLonToPixelRoundTrip) {
    geoslice::GeoTransform geo(test_transform, 36);

    // Test point roughly in center of dataset
    double lat = 31.45;
    double lon = 34.8;

    auto [px, py] = geo.latlon_to_pixel(lat, lon);
    auto [lat2, lon2] = geo.pixel_to_latlon(px, py);

    // Should be close (within 1 pixel * pixel_size)
    EXPECT_NEAR(lat, lat2, 0.001);
    EXPECT_NEAR(lon, lon2, 0.001);
}

TEST_F(GeoTransformTest, FovToPixels) {
    geoslice::GeoTransform geo(test_transform, 36);

    // At 100m altitude with 60 deg FOV
    // Ground width = 2 * 100 * tan(30) = 115.47m
    auto [w, h] = geo.fov_to_pixels(100.0, 60.0);

    // Should be roughly 115.47 / 0.34 = 340 pixels wide
    EXPECT_GT(w, 300);
    EXPECT_LT(w, 400);

    // Higher altitude = larger window
    auto [w2, h2] = geo.fov_to_pixels(200.0, 60.0);
    EXPECT_GT(w2, w);
}

TEST_F(GeoTransformTest, UtmZoneAffectsCentralMeridian) {
    geoslice::GeoTransform geo36(test_transform, 36);
    geoslice::GeoTransform geo35(test_transform, 35);

    double lat = 31.45;
    double lon = 34.8;

    auto [px36, py36] = geo36.latlon_to_pixel(lat, lon);
    auto [px35, py35] = geo35.latlon_to_pixel(lat, lon);

    // Different zones should produce different pixels
    EXPECT_NE(px36, px35);
}

TEST_F(GeoTransformTest, OriginMapping) {
    geoslice::GeoTransform geo(test_transform, 36);

    // UTM origin should map to pixel (0, 0)
    // Test reverse: pixel (0,0) should give us the origin coordinates
    auto [lat, lon] = geo.pixel_to_latlon(0, 0);
    auto [px, py] = geo.latlon_to_pixel(lat, lon);

    EXPECT_EQ(px, 0);
    EXPECT_EQ(py, 0);
}
