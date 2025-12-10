#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "geoslice/geoslice.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_geoslice_cpp, m) {
    m.doc() = "GeoSlice C++ backend for ultra-fast geospatial windowing";
    m.attr("__version__") = geoslice::VERSION;

    py::class_<geoslice::GeoMetadata>(m, "GeoMetadata")
        .def_readonly("dtype", &geoslice::GeoMetadata::dtype)
        .def_readonly("count", &geoslice::GeoMetadata::count)
        .def_readonly("height", &geoslice::GeoMetadata::height)
        .def_readonly("width", &geoslice::GeoMetadata::width)
        .def_readonly("crs", &geoslice::GeoMetadata::crs)
        .def_property_readonly("transform", [](const geoslice::GeoMetadata& m) {
            return std::vector<double>(m.transform.begin(), m.transform.end());
        });

    py::class_<geoslice::MMapReader>(m, "MMapReader")
        .def(py::init<const std::string&>(), py::arg("base_path"))
        .def_property_readonly("width", &geoslice::MMapReader::width)
        .def_property_readonly("height", &geoslice::MMapReader::height)
        .def_property_readonly("bands", &geoslice::MMapReader::bands)
        .def_property_readonly("metadata", &geoslice::MMapReader::metadata)
        .def("is_valid_window", &geoslice::MMapReader::is_valid_window)
        .def("get_window", [](const geoslice::MMapReader& reader, int x, int y, int width, int height) {
            auto view = reader.get_window(x, y, width, height);
            const auto& meta = reader.metadata();

            // Create numpy array that shares memory with mmap
            std::vector<ssize_t> shape = {view.bands, view.height, view.width};
            std::vector<ssize_t> strides = {
                static_cast<ssize_t>(view.stride_band),
                static_cast<ssize_t>(view.stride_row),
                static_cast<ssize_t>(view.pixel_size)
            };

            py::dtype dtype(meta.dtype);
            return py::array(dtype, shape, strides, view.data, py::cast(reader));
        }, py::arg("x"), py::arg("y"), py::arg("width"), py::arg("height"),
           py::return_value_policy::reference_internal);

    py::class_<geoslice::GeoTransform>(m, "GeoTransform")
        .def(py::init<const std::array<double, 6>&, int>(),
             py::arg("transform"), py::arg("utm_zone") = 36)
        .def_property_readonly("pixel_size_x", &geoslice::GeoTransform::pixel_size_x)
        .def_property_readonly("pixel_size_y", &geoslice::GeoTransform::pixel_size_y)
        .def("latlon_to_pixel", &geoslice::GeoTransform::latlon_to_pixel)
        .def("pixel_to_latlon", &geoslice::GeoTransform::pixel_to_latlon)
        .def("fov_to_pixels", &geoslice::GeoTransform::fov_to_pixels);

    py::class_<geoslice::WindowCache>(m, "WindowCache")
        .def(py::init<size_t>(), py::arg("max_bytes") = 256 * 1024 * 1024)
        .def_property_readonly("size", &geoslice::WindowCache::size)
        .def_property_readonly("capacity", &geoslice::WindowCache::capacity)
        .def_property_readonly("hits", &geoslice::WindowCache::hits)
        .def_property_readonly("misses", &geoslice::WindowCache::misses)
        .def("clear", &geoslice::WindowCache::clear);
}
