"""Core GeoSlice functionality."""

from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

# Try C++ backend first
try:
    from ._geoslice_cpp import MMapReader as _CppReader
    from ._geoslice_cpp import GeoTransform as _CppGeoTransform
    _USE_CPP = True
except ImportError:
    _USE_CPP = False


@dataclass
class GeoMetadata:
    """Geospatial metadata for a raster dataset."""
    dtype: str
    count: int
    height: int
    width: int
    transform: Tuple[float, ...]
    crs: Optional[str] = None


class FastGeoMap:
    """
    Zero-copy memory-mapped geospatial raster reader.
    
    Args:
        base_name: Path without extension (expects .bin and .json files)
        use_cpp: Force C++ backend (None = auto-detect)
    
    Example:
        >>> loader = FastGeoMap("processed_map")
        >>> window = loader.get_window(100, 100, 512, 512)
        >>> print(window.shape)  # (bands, height, width)
    """
    
    def __init__(self, base_name: Union[str, Path], use_cpp: Optional[bool] = None):
        self._base_name = str(base_name)
        self._use_cpp = use_cpp if use_cpp is not None else _USE_CPP
        
        json_path = f"{self._base_name}.json"
        bin_path = f"{self._base_name}.bin"
        
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Metadata not found: {json_path}")
        if not os.path.exists(bin_path):
            raise FileNotFoundError(f"Binary data not found: {bin_path}")
        
        with open(json_path, "r") as f:
            meta_dict = json.load(f)
        
        self.meta = GeoMetadata(
            dtype=meta_dict["dtype"],
            count=meta_dict["count"],
            height=meta_dict["height"],
            width=meta_dict["width"],
            transform=tuple(meta_dict["transform"]),
            crs=meta_dict.get("crs"),
        )
        
        if self._use_cpp:
            self._reader = _CppReader(self._base_name)
        else:
            self._shape = (self.meta.count, self.meta.height, self.meta.width)
            self._dtype = np.dtype(self.meta.dtype)
            self._data = np.memmap(bin_path, dtype=self._dtype, mode='r', shape=self._shape)
    
    @property
    def width(self) -> int:
        return self.meta.width
    
    @property
    def height(self) -> int:
        return self.meta.height
    
    @property
    def bands(self) -> int:
        return self.meta.count
    
    @property
    def shape(self) -> Tuple[int, int, int]:
        return (self.meta.count, self.meta.height, self.meta.width)
    
    def is_valid_window(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if window coordinates are within bounds."""
        return (x >= 0 and y >= 0 and 
                x + width <= self.meta.width and 
                y + height <= self.meta.height and
                width > 0 and height > 0)
    
    def get_window(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """
        Get a zero-copy view of a rectangular window.
        
        Args:
            x: Column offset (left edge)
            y: Row offset (top edge)
            width: Window width in pixels
            height: Window height in pixels
            
        Returns:
            NumPy array view with shape (bands, height, width)
        """
        if self._use_cpp:
            return self._reader.get_window(x, y, width, height)
        
        # Clamp to bounds
        x = max(0, x)
        y = max(0, y)
        width = min(width, self.meta.width - x)
        height = min(height, self.meta.height - y)
        
        if width <= 0 or height <= 0:
            return np.empty((self.meta.count, 0, 0), dtype=self._dtype)
        
        return self._data[:, y:y+height, x:x+width]
    
    def get_window_copy(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Get a copy of a window (safe for modification)."""
        return np.array(self.get_window(x, y, width, height))


class GeoTransform:
    """
    Coordinate transformation between lat/lon and pixel coordinates.
    
    Args:
        transform: 6-element affine transform tuple
        utm_zone: UTM zone number (default: 36)
    """
    
    _WGS84_A = 6378137.0
    _WGS84_F = 1 / 298.257223563
    _UTM_K0 = 0.9996
    
    def __init__(self, transform: Tuple[float, ...], utm_zone: int = 36):
        if _USE_CPP:
            import array
            arr = array.array('d', transform[:6])
            self._cpp = _CppGeoTransform(arr, utm_zone)
        else:
            self._cpp = None
            
        self.pixel_size_x = transform[0]
        self.pixel_size_y = abs(transform[4])
        self.origin_x = transform[2]
        self.origin_y = transform[5]
        self.utm_zone = utm_zone
        self.central_meridian = (utm_zone - 1) * 6 - 180 + 3
    
    def latlon_to_pixel(self, lat: float, lon: float) -> Tuple[int, int]:
        """Convert lat/lon to pixel coordinates."""
        if self._cpp:
            return self._cpp.latlon_to_pixel(lat, lon)
        
        utm_x, utm_y = self._latlon_to_utm(lat, lon)
        px = int((utm_x - self.origin_x) / self.pixel_size_x)
        py = int((self.origin_y - utm_y) / self.pixel_size_y)
        return px, py
    
    def pixel_to_latlon(self, px: int, py: int) -> Tuple[float, float]:
        """Convert pixel coordinates to lat/lon."""
        if self._cpp:
            return self._cpp.pixel_to_latlon(px, py)
        
        utm_x = self.origin_x + px * self.pixel_size_x
        utm_y = self.origin_y - py * self.pixel_size_y
        return self._utm_to_latlon(utm_x, utm_y)
    
    def fov_to_pixels(self, altitude_m: float, fov_deg: float) -> Tuple[int, int]:
        """Calculate pixel dimensions for a given altitude and FOV."""
        if self._cpp:
            return self._cpp.fov_to_pixels(altitude_m, fov_deg)
        
        ground_width = 2 * altitude_m * math.tan(math.radians(fov_deg / 2))
        return int(ground_width / self.pixel_size_x), int(ground_width / self.pixel_size_y)
    
    def _latlon_to_utm(self, lat: float, lon: float) -> Tuple[float, float]:
        e2 = 2 * self._WGS84_F - self._WGS84_F ** 2
        e_prime2 = e2 / (1 - e2)
        
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        lon0_rad = math.radians(self.central_meridian)
        
        N = self._WGS84_A / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        T = math.tan(lat_rad)**2
        C = e_prime2 * math.cos(lat_rad)**2
        A = (lon_rad - lon0_rad) * math.cos(lat_rad)
        
        M = self._WGS84_A * ((1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_rad
                - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_rad)
                + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_rad)
                - (35*e2**3/3072) * math.sin(6*lat_rad))
        
        x = self._UTM_K0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58*e_prime2)*A**5/120) + 500000
        y = self._UTM_K0 * (M + N * math.tan(lat_rad) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24 
                  + (61-58*T+T**2+600*C-330*e_prime2)*A**6/720))
        return x, y
    
    def _utm_to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        e2 = 2 * self._WGS84_F - self._WGS84_F ** 2
        e1 = (1 - math.sqrt(1-e2)) / (1 + math.sqrt(1-e2))
        
        x -= 500000
        M = y / self._UTM_K0
        mu = M / (self._WGS84_A * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))
        
        phi1 = mu + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu) \
               + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu) \
               + (151*e1**3/96) * math.sin(6*mu)
        
        N1 = self._WGS84_A / math.sqrt(1 - e2*math.sin(phi1)**2)
        T1 = math.tan(phi1)**2
        C1 = (e2/(1-e2)) * math.cos(phi1)**2
        R1 = self._WGS84_A * (1-e2) / (1 - e2*math.sin(phi1)**2)**1.5
        D = x / (N1 * self._UTM_K0)
        
        lat = phi1 - (N1*math.tan(phi1)/R1) * (D**2/2 - (5+3*T1+10*C1-4*C1**2-9*(e2/(1-e2)))*D**4/24
                      + (61+90*T1+298*C1+45*T1**2-252*(e2/(1-e2))-3*C1**2)*D**6/720)
        lon = math.radians(self.central_meridian) + (D - (1+2*T1+C1)*D**3/6 
                      + (5-2*C1+28*T1-3*C1**2+8*(e2/(1-e2))+24*T1**2)*D**5/120) / math.cos(phi1)
        
        return math.degrees(lat), math.degrees(lon)


def convert_tif_to_raw(
    input_path: Union[str, Path],
    output_base: Union[str, Path],
    overwrite: bool = False,
) -> Tuple[str, str]:
    """
    Convert a GeoTIFF to raw binary format for memory mapping.
    
    Args:
        input_path: Path to input GeoTIFF
        output_base: Base path for output (without extension)
        overwrite: Overwrite existing files
        
    Returns:
        Tuple of (bin_path, json_path)
    """
    import rasterio
    
    input_path = str(input_path)
    output_base = str(output_base)
    bin_path = f"{output_base}.bin"
    json_path = f"{output_base}.json"
    
    if not overwrite and (os.path.exists(bin_path) or os.path.exists(json_path)):
        raise FileExistsError(f"Output files already exist: {output_base}.*")
    
    # Convert using GDAL
    cmd = [
        "gdal_translate",
        "-of", "ENVI",
        "-co", "INTERLEAVE=BSQ",
        input_path,
        bin_path,
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Extract metadata
    with rasterio.open(input_path) as src:
        metadata = {
            "dtype": src.profile["dtype"],
            "count": src.count,
            "height": src.height,
            "width": src.width,
            "transform": list(src.transform)[:6],
            "crs": src.crs.to_string() if src.crs else None,
        }
    
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Clean up ENVI header (optional)
    hdr_path = f"{bin_path}.hdr" if os.path.exists(f"{bin_path}.hdr") else bin_path.replace(".bin", ".hdr")
    if os.path.exists(hdr_path):
        os.remove(hdr_path)
    
    return bin_path, json_path
