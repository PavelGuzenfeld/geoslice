# GeoSlice

Ultra-fast geospatial windowing with zero-copy memory mapping.

[![CI](https://github.com/yourusername/geoslice/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/geoslice/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/geoslice.svg)](https://pypi.org/project/geoslice/)
[![Python](https://img.shields.io/pypi/pyversions/geoslice.svg)](https://pypi.org/project/geoslice/)

## Performance

### Head-to-Head: GeoSlice vs Rasterio

```
============================================================
COMPARISON: 100 x 512x512 windows (4096x4096 4-band image)
============================================================
Method               Time (s)     Ops/s        Speedup
------------------------------------------------------------
GeoSlice (mmap)      0.0003       305,737      154.6x
Rasterio             0.0506       1,977        1.0x
============================================================
```

### Detailed Benchmarks

| Test | GeoSlice | Rasterio | Speedup |
|------|----------|----------|---------|
| Single 512x512 window | 1.4μs (690k ops/s) | 170μs (5.9k ops/s) | **117x** |
| 100 sequential windows | 129μs (7.7k ops/s) | 16.6ms (60 ops/s) | **128x** |
| 100 random windows | 126μs (8.0k ops/s) | 30.4ms (33 ops/s) | **241x** |
| 50-waypoint flight sim | 24μs (41k ops/s) | 1.4ms (707 ops/s) | **59x** |

### Coordinate Transform Performance

| Operation | Time | Throughput |
|-----------|------|------------|
| latlon→pixel (×1000) | 2.0ms | 494 ops/s |
| FOV→pixels (×1000) | 203μs | 4,937 ops/s |

## Install

```bash
pip install geoslice
```

For converting GeoTIFFs:
```bash
pip install geoslice[convert]
sudo apt install gdal-bin  # Linux
```

## Quick Start

### 1. Convert GeoTIFF (one-time)

```python
from geoslice import convert_tif_to_raw

convert_tif_to_raw("input.tif", "output_map")
# Creates: output_map.bin, output_map.json
```

Or via CLI:
```bash
gdal_translate -of ENVI -co INTERLEAVE=BSQ input.tif output_map.bin
```

### 2. Access Windows

```python
from geoslice import FastGeoMap

loader = FastGeoMap("output_map")

# Zero-copy window access (~690k ops/s)
window = loader.get_window(x=100, y=100, width=512, height=512)
print(window.shape)  # (bands, height, width)
```

### 3. Drone Simulation

```python
from geoslice import FastGeoMap, GeoTransform, FlightPath

loader = FastGeoMap("output_map")
geo = GeoTransform(loader.meta.transform, utm_zone=36)

# Generate spiral flight path
path = FlightPath.spiral(
    center_lat=31.45,
    center_lon=34.80,
    num_waypoints=50,
    altitudes=[50, 100, 150, 200],
)

# Extract windows along path (~41k waypoints/sec)
for state in path:
    win = FlightPath.state_to_window(state, geo)
    if win.is_valid(loader.width, loader.height):
        data = loader.get_window(win.x, win.y, win.width, win.height)
        # Process frame...
```

## API

### FastGeoMap

```python
FastGeoMap(base_name: str, use_cpp: bool = None)
```

- `get_window(x, y, width, height)` → `np.ndarray` (view, zero-copy)
- `get_window_copy(x, y, width, height)` → `np.ndarray` (copy)
- `is_valid_window(x, y, width, height)` → `bool`
- `.width`, `.height`, `.bands`, `.shape`, `.meta`

### GeoTransform

```python
GeoTransform(transform: tuple, utm_zone: int = 36)
```

- `latlon_to_pixel(lat, lon)` → `(px, py)`
- `pixel_to_latlon(px, py)` → `(lat, lon)`
- `fov_to_pixels(altitude_m, fov_deg)` → `(width, height)`

### FlightPath

```python
FlightPath.spiral(center_lat, center_lon, num_waypoints, altitudes, fov_deg)
FlightPath.linear(start_lat, start_lon, end_lat, end_lon, num_waypoints, altitude_m)
FlightPath.grid(min_lat, min_lon, max_lat, max_lon, rows, cols, altitude_m)
```

- `state_to_window(state, geo)` → `WindowParams`
- `compute_windows(geo)` → `List[WindowParams]`

## How It Works

**Rasterio (standard approach):**
```
Seek → Read → Decompress → Allocate → Copy to RAM
```

**GeoSlice (mmap approach):**
```
Pointer arithmetic → OS pages in 4KB chunks on-demand
```

The OS kernel handles caching, prefetching, and memory management. Random access is **241x faster** because there's no decompression overhead.

## Development

### Setup

```bash
git clone https://github.com/yourusername/geoslice
cd geoslice

# Create venv (use --system-site-packages if you need ROS2)
python3 -m venv .venv --system-site-packages
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Run Tests

```bash
# All tests
pytest -v

# Benchmarks with comparison table
pytest tests/test_benchmark.py -v -s

# Just the comparison report
pytest tests/test_benchmark.py::TestDirectComparison -v -s

# Detailed benchmark stats
pytest tests/test_benchmark.py --benchmark-only --benchmark-columns=min,max,mean,ops
```

### Build C++ (optional)

```bash
cmake -B build -DBUILD_PYTHON=OFF
cmake --build build
ctest --test-dir build --output-on-failure
```

## C++ Usage

```cpp
#include <geoslice/geoslice.hpp>

geoslice::MMapReader reader("processed_map");
auto view = reader.get_window(100, 100, 512, 512);

// Zero-copy access
uint8_t pixel = view.at<uint8_t>(0, 0, 0);  // band, y, x
```

## Release

Releases are automated via GitHub Actions on version tags:

```bash
# Update version in pyproject.toml and python/geoslice/__init__.py
git add -A
git commit -m "Release v0.0.2"
git tag v0.0.2
git push && git push --tags
```

## License

MIT License. See `LICENSE` file for details.
