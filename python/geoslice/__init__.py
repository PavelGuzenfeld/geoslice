"""GeoSlice: Ultra-fast geospatial windowing with zero-copy memory mapping."""

__version__ = "0.0.1"

from .core import FastGeoMap, GeoTransform, convert_tif_to_raw
from .drone import DroneState, FlightPath

__all__ = [
    "FastGeoMap",
    "GeoTransform", 
    "DroneState",
    "FlightPath",
    "convert_tif_to_raw",
]

# Try to import C++ backend
try:
    from ._geoslice_cpp import MMapReader as _CppMMapReader
    from ._geoslice_cpp import GeoTransform as _CppGeoTransform
    HAS_CPP_BACKEND = True
except ImportError:
    HAS_CPP_BACKEND = False
