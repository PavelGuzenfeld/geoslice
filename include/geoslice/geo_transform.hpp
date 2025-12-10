#pragma once

#include <cmath>
#include <array>
#include <utility>

namespace geoslice {

class GeoTransform {
public:
    GeoTransform(const std::array<double, 6>& transform, int utm_zone = 36);
    
    std::pair<int, int> latlon_to_pixel(double lat, double lon) const;
    std::pair<double, double> pixel_to_latlon(int px, int py) const;
    std::pair<int, int> fov_to_pixels(double altitude_m, double fov_deg) const;
    
    double pixel_size_x() const { return pixel_size_x_; }
    double pixel_size_y() const { return pixel_size_y_; }

private:
    std::pair<double, double> latlon_to_utm(double lat, double lon) const;
    std::pair<double, double> utm_to_latlon(double x, double y) const;
    
    double pixel_size_x_;
    double pixel_size_y_;
    double origin_x_;
    double origin_y_;
    int utm_zone_;
    double central_meridian_;
};

// Inline utility
inline double deg2rad(double deg) { return deg * M_PI / 180.0; }
inline double rad2deg(double rad) { return rad * 180.0 / M_PI; }

} // namespace geoslice
