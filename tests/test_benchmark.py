"""Benchmark tests for geoslice."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from geoslice import FastGeoMap, GeoTransform, FlightPath


@pytest.fixture(scope="module")
def large_test_data():
    """Create larger test dataset for benchmarking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "bench_map"
        
        # 4K-ish resolution
        height, width = 2160, 3840
        bands = 4
        
        meta = {
            "dtype": "uint8",
            "count": bands,
            "height": height,
            "width": width,
            "transform": [0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0],
            "crs": "EPSG:32636"
        }
        with open(f"{base}.json", "w") as f:
            json.dump(meta, f)
        
        data = np.random.randint(0, 255, (bands, height, width), dtype=np.uint8)
        data.tofile(f"{base}.bin")
        
        yield str(base)


class TestBenchmarks:
    def test_window_access_speed(self, large_test_data, benchmark):
        """Benchmark single window access."""
        loader = FastGeoMap(large_test_data, use_cpp=False)
        
        def access_window():
            return loader.get_window(100, 100, 512, 512)
        
        result = benchmark(access_window)
        assert result.shape == (4, 512, 512)
    
    def test_sequential_windows(self, large_test_data, benchmark):
        """Benchmark sequential window access (simulating video frames)."""
        loader = FastGeoMap(large_test_data, use_cpp=False)
        
        def access_sequence():
            windows = []
            for i in range(100):
                x, y = i * 10, i * 10
                w = loader.get_window(x, y, 256, 256)
                _ = w[0, 0, 0]  # Touch data
                windows.append(w)
            return windows
        
        benchmark(access_sequence)
    
    def test_random_windows(self, large_test_data, benchmark):
        """Benchmark random window access."""
        loader = FastGeoMap(large_test_data, use_cpp=False)
        np.random.seed(42)
        
        coords = [
            (np.random.randint(0, 3000), np.random.randint(0, 1500))
            for _ in range(100)
        ]
        
        def access_random():
            for x, y in coords:
                w = loader.get_window(x, y, 256, 256)
                _ = w[0, 0, 0]
        
        benchmark(access_random)
    
    def test_flight_path_simulation(self, large_test_data, benchmark):
        """Benchmark full flight path simulation."""
        loader = FastGeoMap(large_test_data, use_cpp=False)
        geo = GeoTransform(loader.meta.transform, utm_zone=36)
        
        center_lat, center_lon = geo.pixel_to_latlon(1920, 1080)
        path = FlightPath.spiral(center_lat, center_lon, num_waypoints=50)
        windows = path.compute_windows(geo)
        
        def simulate_flight():
            for win in windows:
                if win.is_valid(loader.width, loader.height):
                    data = loader.get_window(win.x, win.y, win.width, win.height)
                    _ = data[0, 0, 0]
        
        benchmark(simulate_flight)
    
    def test_geo_transform_speed(self, benchmark):
        """Benchmark coordinate transformations."""
        transform = (0.5, 0.0, 500000.0, 0.0, -0.5, 3500000.0)
        geo = GeoTransform(transform, utm_zone=36)
        
        coords = [(31.0 + i * 0.01, 34.0 + i * 0.01) for i in range(1000)]
        
        def transform_coords():
            for lat, lon in coords:
                geo.latlon_to_pixel(lat, lon)
        
        benchmark(transform_coords)
