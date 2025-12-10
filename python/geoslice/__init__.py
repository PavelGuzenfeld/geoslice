"""GeoSlice: Ultra-fast geospatial windowing with zero-copy memory mapping."""

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0.dev0"  # Fallback for editable installs without build

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
    from ._geoslice_cpp import GeoTransform as _CppGeoTransform  # noqa: F401
    from ._geoslice_cpp import MMapReader as _CppMMapReader  # noqa: F401

    HAS_CPP_BACKEND = True
except ImportError:
    HAS_CPP_BACKEND = False
