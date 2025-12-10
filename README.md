# GeoSlice

Ultra-fast geospatial windowing with zero-copy memory mapping.

[![CI](https://github.com/yourusername/geoslice/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/geoslice/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/geoslice.svg)](https://pypi.org/project/geoslice/)
[![Python](https://img.shields.io/pypi/pyversions/geoslice.svg)](https://pypi.org/project/geoslice/)

## Performance

### vs Rasterio (real-world GeoTIFF)

| Method | Throughput | Speedup |
|--------|------------|---------|
| **GeoSlice (mmap)** | ~600k ops/s | **213x** |
| Rasterio | ~2.7k ops/s | 1x |

### Micro-benchmarks (synthetic data)

```
Name                          Mean        Ops/s       Notes
─────────────────────────────────────────────────────────────
window_access_speed           1.3μs       761,344     Single 512x512 window
flight_path_simulation        15.2μs      65,551      50 waypoints pipeline
random_windows                131.8μs     7,585       100 random positions
sequential_windows            139.9μs     7,145       100 sequential windows
geo_transform_speed           2.1ms       475         1000 coord transforms
```

## Install

```bash
pip install geoslice
```

With C++ backend (recommended):
```bash
pip install geoslice[cpp]
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

# Zero-copy window access (~760k ops/s)
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

# Extract windows along path
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

Standard libraries (Rasterio, OpenCV) read compressed data:
```
Seek → Read → Decompress → Copy to RAM
```

GeoSlice uses memory-mapped raw binary:
```
Pointer arithmetic → OS pages in 4KB chunks on-demand
```

The OS kernel handles caching, prefetching, and memory management.

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
# Python tests
pytest -v

# With benchmark details
pytest -v --benchmark-only

# C++ tests (requires build)
cmake -B build -DBUILD_PYTHON=OFF
cmake --build build
ctest --test-dir build --output-on-failure
```

### Test with Real Data

```bash
# Convert your GeoTIFF
python -c "from geoslice import convert_tif_to_raw; convert_tif_to_raw('your_image.tif', 'processed_map')"

# Benchmark
python -c "
from geoslice import FastGeoMap
import time

loader = FastGeoMap('processed_map')
print(f'Loaded: {loader.shape}')

start = time.perf_counter()
for i in range(1000):
    w = loader.get_window(i*10 % 1000, i*10 % 1000, 512, 512)
    _ = w[0,0,0]
elapsed = time.perf_counter() - start
print(f'1000 windows: {elapsed:.4f}s ({1000/elapsed:.0f} ops/s)')
"
```

## C++ Usage

```cpp
#include <geoslice/geoslice.hpp>

geoslice::MMapReader reader("processed_map");
auto view = reader.get_window(100, 100, 512, 512);

// Zero-copy access
uint8_t pixel = view.at<uint8_t>(0, 0, 0);  // band, y, x
```

Build:
```bash
cmake -B build -DBUILD_PYTHON=OFF
cmake --build build
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