#include "geoslice/geo_transform.hpp"
#include <cmath>

namespace geoslice {

namespace {
constexpr double WGS84_A = 6378137.0;
constexpr double WGS84_F = 1.0 / 298.257223563;
constexpr double UTM_K0 = 0.9996;
}

GeoTransform::GeoTransform(const std::array<double, 6>& transform, int utm_zone)
    : pixel_size_x_(transform[0])
    , pixel_size_y_(std::abs(transform[4]))
    , origin_x_(transform[2])
    , origin_y_(transform[5])
    , utm_zone_(utm_zone)
    , central_meridian_((utm_zone - 1) * 6 - 180 + 3) {}

std::pair<double, double> GeoTransform::latlon_to_utm(double lat, double lon) const {
    double e2 = 2 * WGS84_F - WGS84_F * WGS84_F;
    double e_prime2 = e2 / (1 - e2);
    
    double lat_rad = deg2rad(lat);
    double lon_rad = deg2rad(lon);
    double lon0_rad = deg2rad(central_meridian_);
    
    double N = WGS84_A / std::sqrt(1 - e2 * std::sin(lat_rad) * std::sin(lat_rad));
    double T = std::tan(lat_rad) * std::tan(lat_rad);
    double C = e_prime2 * std::cos(lat_rad) * std::cos(lat_rad);
    double A = (lon_rad - lon0_rad) * std::cos(lat_rad);
    
    double M = WGS84_A * ((1 - e2/4 - 3*e2*e2/64 - 5*e2*e2*e2/256) * lat_rad
                - (3*e2/8 + 3*e2*e2/32 + 45*e2*e2*e2/1024) * std::sin(2*lat_rad)
                + (15*e2*e2/256 + 45*e2*e2*e2/1024) * std::sin(4*lat_rad)
                - (35*e2*e2*e2/3072) * std::sin(6*lat_rad));
    
    double x = UTM_K0 * N * (A + (1-T+C)*A*A*A/6 + (5-18*T+T*T+72*C-58*e_prime2)*A*A*A*A*A/120) + 500000;
    double y = UTM_K0 * (M + N * std::tan(lat_rad) * (A*A/2 + (5-T+9*C+4*C*C)*A*A*A*A/24 
              + (61-58*T+T*T+600*C-330*e_prime2)*A*A*A*A*A*A/720));
    
    return {x, y};
}

std::pair<double, double> GeoTransform::utm_to_latlon(double x, double y) const {
    double e2 = 2 * WGS84_F - WGS84_F * WGS84_F;
    double e1 = (1 - std::sqrt(1-e2)) / (1 + std::sqrt(1-e2));
    
    x -= 500000;
    double M = y / UTM_K0;
    double mu = M / (WGS84_A * (1 - e2/4 - 3*e2*e2/64 - 5*e2*e2*e2/256));
    
    double phi1 = mu + (3*e1/2 - 27*e1*e1*e1/32) * std::sin(2*mu)
                 + (21*e1*e1/16 - 55*e1*e1*e1*e1/32) * std::sin(4*mu)
                 + (151*e1*e1*e1/96) * std::sin(6*mu);
    
    double N1 = WGS84_A / std::sqrt(1 - e2*std::sin(phi1)*std::sin(phi1));
    double T1 = std::tan(phi1) * std::tan(phi1);
    double C1 = (e2/(1-e2)) * std::cos(phi1) * std::cos(phi1);
    double R1 = WGS84_A * (1-e2) / std::pow(1 - e2*std::sin(phi1)*std::sin(phi1), 1.5);
    double D = x / (N1 * UTM_K0);
    
    double lat = phi1 - (N1*std::tan(phi1)/R1) * (D*D/2 - (5+3*T1+10*C1-4*C1*C1-9*(e2/(1-e2)))*D*D*D*D/24
                  + (61+90*T1+298*C1+45*T1*T1-252*(e2/(1-e2))-3*C1*C1)*D*D*D*D*D*D/720);
    double lon = deg2rad(central_meridian_) + (D - (1+2*T1+C1)*D*D*D/6 
                  + (5-2*C1+28*T1-3*C1*C1+8*(e2/(1-e2))+24*T1*T1)*D*D*D*D*D/120) / std::cos(phi1);
    
    return {rad2deg(lat), rad2deg(lon)};
}

std::pair<int, int> GeoTransform::latlon_to_pixel(double lat, double lon) const {
    auto [utm_x, utm_y] = latlon_to_utm(lat, lon);
    int px = static_cast<int>((utm_x - origin_x_) / pixel_size_x_);
    int py = static_cast<int>((origin_y_ - utm_y) / pixel_size_y_);
    return {px, py};
}

std::pair<double, double> GeoTransform::pixel_to_latlon(int px, int py) const {
    double utm_x = origin_x_ + px * pixel_size_x_;
    double utm_y = origin_y_ - py * pixel_size_y_;
    return utm_to_latlon(utm_x, utm_y);
}

std::pair<int, int> GeoTransform::fov_to_pixels(double altitude_m, double fov_deg) const {
    double ground_width = 2 * altitude_m * std::tan(deg2rad(fov_deg / 2));
    int px_width = static_cast<int>(ground_width / pixel_size_x_);
    int px_height = static_cast<int>(ground_width / pixel_size_y_);
    return {px_width, px_height};
}

} // namespace geoslice
