"""Benchmark tests for geoslice vs rasterio."""

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from geoslice import FastGeoMap, GeoTransform, FlightPath

# Check if rasterio is available
try:
    import rasterio
    from rasterio.windows import Window
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


@pytest.fixture(scope="module")
def test_data_pair():
    """Create matching GeoTIFF and raw binary for fair comparison."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        height, width = 4096, 4096
        bands = 4
        
        # Create raw binary + json (geoslice format)
        raw_base = base / "bench_map"
        meta = {
            "dtype": "uint8",
            "count": bands,
            "height": height,
            "width": width,
            "transform": [0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0],
            "crs": "EPSG:32636"
        }
        with open(f"{raw_base}.json", "w") as f:
            json.dump(meta, f)
        
        data = np.random.randint(0, 255, (bands, height, width), dtype=np.uint8)
        data.tofile(f"{raw_base}.bin")
        
        # Create GeoTIFF (rasterio format)
        tif_path = base / "bench_map.tif"
        if HAS_RASTERIO:
            from rasterio.transform import from_bounds
            transform = rasterio.transform.Affine(0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0)
            with rasterio.open(
                tif_path, 'w',
                driver='GTiff',
                height=height, width=width,
                count=bands,
                dtype='uint8',
                crs='EPSG:32636',
                transform=transform,
            ) as dst:
                dst.write(data)
        
        yield {
            "raw_base": str(raw_base),
            "tif_path": str(tif_path),
            "height": height,
            "width": width,
        }


class TestGeosliceBenchmarks:
    """Benchmarks for geoslice (mmap) implementation."""
    
    def test_geoslice_single_window(self, test_data_pair, benchmark):
        """Single window access."""
        loader = FastGeoMap(test_data_pair["raw_base"], use_cpp=False)
        
        def access():
            w = loader.get_window(100, 100, 512, 512)
            _ = w[0, 0, 0]
            return w
        
        result = benchmark(access)
        assert result.shape == (4, 512, 512)
    
    def test_geoslice_sequential_100(self, test_data_pair, benchmark):
        """100 sequential windows."""
        loader = FastGeoMap(test_data_pair["raw_base"], use_cpp=False)
        
        def access_seq():
            for i in range(100):
                w = loader.get_window(i * 10, i * 10, 512, 512)
                _ = w[0, 0, 0]
        
        benchmark(access_seq)
    
    def test_geoslice_random_100(self, test_data_pair, benchmark):
        """100 random windows."""
        loader = FastGeoMap(test_data_pair["raw_base"], use_cpp=False)
        np.random.seed(42)
        coords = [(np.random.randint(0, 3000), np.random.randint(0, 3000)) for _ in range(100)]
        
        def access_rand():
            for x, y in coords:
                w = loader.get_window(x, y, 512, 512)
                _ = w[0, 0, 0]
        
        benchmark(access_rand)


@pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
class TestRasterioBenchmarks:
    """Benchmarks for rasterio (standard) implementation."""
    
    def test_rasterio_single_window(self, test_data_pair, benchmark):
        """Single window access."""
        src = rasterio.open(test_data_pair["tif_path"])
        
        def access():
            w = src.read(window=Window(100, 100, 512, 512))
            _ = w[0, 0, 0]
            return w
        
        result = benchmark(access)
        assert result.shape == (4, 512, 512)
        src.close()
    
    def test_rasterio_sequential_100(self, test_data_pair, benchmark):
        """100 sequential windows."""
        src = rasterio.open(test_data_pair["tif_path"])
        
        def access_seq():
            for i in range(100):
                w = src.read(window=Window(i * 10, i * 10, 512, 512))
                _ = w[0, 0, 0]
        
        benchmark(access_seq)
        src.close()
    
    def test_rasterio_random_100(self, test_data_pair, benchmark):
        """100 random windows."""
        src = rasterio.open(test_data_pair["tif_path"])
        np.random.seed(42)
        coords = [(np.random.randint(0, 3000), np.random.randint(0, 3000)) for _ in range(100)]
        
        def access_rand():
            for x, y in coords:
                w = src.read(window=Window(x, y, 512, 512))
                _ = w[0, 0, 0]
        
        benchmark(access_rand)
        src.close()


class TestGeoTransformBenchmarks:
    """Benchmarks for coordinate transformations."""
    
    def test_geo_latlon_to_pixel_1000(self, benchmark):
        """1000 latlon→pixel conversions."""
        geo = GeoTransform((0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0), utm_zone=36)
        coords = [(31.0 + i * 0.001, 34.0 + i * 0.001) for i in range(1000)]
        
        def convert():
            for lat, lon in coords:
                geo.latlon_to_pixel(lat, lon)
        
        benchmark(convert)
    
    def test_geo_fov_to_pixels_1000(self, benchmark):
        """1000 FOV→pixel conversions."""
        geo = GeoTransform((0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0), utm_zone=36)
        altitudes = [50 + i % 200 for i in range(1000)]
        
        def convert():
            for alt in altitudes:
                geo.fov_to_pixels(alt, 60.0)
        
        benchmark(convert)


class TestFlightPathBenchmarks:
    """Benchmarks for flight simulation pipeline."""
    
    def test_flight_path_50_waypoints(self, test_data_pair, benchmark):
        """Full pipeline: 50 waypoint spiral."""
        loader = FastGeoMap(test_data_pair["raw_base"], use_cpp=False)
        geo = GeoTransform(loader.meta.transform, utm_zone=36)
        center_lat, center_lon = geo.pixel_to_latlon(2048, 2048)
        
        path = FlightPath.spiral(center_lat, center_lon, num_waypoints=50)
        windows = path.compute_windows(geo)
        
        def simulate():
            for win in windows:
                if win.is_valid(loader.width, loader.height):
                    data = loader.get_window(win.x, win.y, win.width, win.height)
                    _ = data[0, 0, 0]
        
        benchmark(simulate)
    
    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_flight_path_50_waypoints_rasterio(self, test_data_pair, benchmark):
        """Full pipeline with rasterio: 50 waypoint spiral."""
        src = rasterio.open(test_data_pair["tif_path"])
        geo = GeoTransform((0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0), utm_zone=36)
        center_lat, center_lon = geo.pixel_to_latlon(2048, 2048)
        
        path = FlightPath.spiral(center_lat, center_lon, num_waypoints=50)
        windows = path.compute_windows(geo)
        
        def simulate():
            for win in windows:
                if win.is_valid(src.width, src.height):
                    data = src.read(window=Window(win.x, win.y, win.width, win.height))
                    _ = data[0, 0, 0]
        
        benchmark(simulate)
        src.close()


# Direct comparison test (not using pytest-benchmark, prints results)
@pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
class TestDirectComparison:
    """Direct head-to-head comparison with printed results."""
    
    def test_comparison_report(self, test_data_pair):
        """Print comparison table."""
        import time
        
        iterations = 100
        window_size = 512
        
        # Setup
        loader = FastGeoMap(test_data_pair["raw_base"], use_cpp=False)
        src = rasterio.open(test_data_pair["tif_path"])
        
        np.random.seed(42)
        coords = [(np.random.randint(0, 3000), np.random.randint(0, 3000)) 
                  for _ in range(iterations)]
        
        # Benchmark geoslice
        t0 = time.perf_counter()
        for x, y in coords:
            w = loader.get_window(x, y, window_size, window_size)
            _ = w[0, 0, 0]
        geoslice_time = time.perf_counter() - t0
        
        # Benchmark rasterio
        t0 = time.perf_counter()
        for x, y in coords:
            w = src.read(window=Window(x, y, window_size, window_size))
            _ = w[0, 0, 0]
        rasterio_time = time.perf_counter() - t0
        
        src.close()
        
        # Print results
        print("\n")
        print("=" * 60)
        print(f"COMPARISON: {iterations} x {window_size}x{window_size} windows")
        print("=" * 60)
        print(f"{'Method':<20} {'Time (s)':<12} {'Ops/s':<12} {'Speedup':<10}")
        print("-" * 60)
        print(f"{'GeoSlice (mmap)':<20} {geoslice_time:<12.4f} {iterations/geoslice_time:<12.0f} {rasterio_time/geoslice_time:<10.1f}x")
        print(f"{'Rasterio':<20} {rasterio_time:<12.4f} {iterations/rasterio_time:<12.0f} {'1.0':<10}")
        print("=" * 60)
        
        # Assert geoslice is faster
        assert geoslice_time < rasterio_time, "GeoSlice should be faster than Rasterio"