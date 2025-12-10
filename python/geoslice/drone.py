"""Drone simulation and flight path utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .core import FastGeoMap, GeoTransform


@dataclass
class DroneState:
    """State of a drone at a single point in time."""
    lat: float
    lon: float
    altitude_m: float
    heading_deg: float = 0.0
    fov_deg: float = 60.0
    speed_ms: float = 0.0
    timestamp: float = 0.0


@dataclass
class WindowParams:
    """Pixel window parameters."""
    x: int
    y: int
    width: int
    height: int
    
    def is_valid(self, map_width: int, map_height: int) -> bool:
        return (self.x >= 0 and self.y >= 0 and
                self.x + self.width <= map_width and
                self.y + self.height <= map_height)


class FlightPath:
    """
    Generate and manage drone flight paths.
    
    Example:
        >>> path = FlightPath.spiral(center_lat, center_lon, num_waypoints=50)
        >>> for state in path:
        ...     window = path.state_to_window(state, geo_transform)
    """
    
    def __init__(self, waypoints: List[DroneState]):
        self.waypoints = waypoints
    
    def __len__(self) -> int:
        return len(self.waypoints)
    
    def __iter__(self):
        return iter(self.waypoints)
    
    def __getitem__(self, idx: int) -> DroneState:
        return self.waypoints[idx]
    
    @classmethod
    def spiral(
        cls,
        center_lat: float,
        center_lon: float,
        num_waypoints: int = 20,
        altitudes: Optional[List[float]] = None,
        radius_deg: float = 0.001,
        fov_deg: float = 60.0,
    ) -> "FlightPath":
        """Generate a spiral flight path around a center point."""
        if altitudes is None:
            altitudes = [50, 100, 150, 200, 250]
        
        waypoints = []
        headings = np.linspace(0, 360, num_waypoints, endpoint=False)
        
        for i in range(num_waypoints):
            radius = radius_deg * (i + 1)
            angle = np.radians(headings[i])
            
            waypoints.append(DroneState(
                lat=center_lat + radius * np.cos(angle),
                lon=center_lon + radius * np.sin(angle),
                altitude_m=altitudes[i % len(altitudes)],
                heading_deg=headings[i],
                fov_deg=fov_deg,
                timestamp=float(i),
            ))
        
        return cls(waypoints)
    
    @classmethod
    def linear(
        cls,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        num_waypoints: int = 20,
        altitude_m: float = 100.0,
        fov_deg: float = 60.0,
    ) -> "FlightPath":
        """Generate a linear flight path between two points."""
        lats = np.linspace(start_lat, end_lat, num_waypoints)
        lons = np.linspace(start_lon, end_lon, num_waypoints)
        heading = math.degrees(math.atan2(end_lon - start_lon, end_lat - start_lat))
        
        waypoints = [
            DroneState(
                lat=lat, lon=lon,
                altitude_m=altitude_m,
                heading_deg=heading,
                fov_deg=fov_deg,
                timestamp=float(i),
            )
            for i, (lat, lon) in enumerate(zip(lats, lons))
        ]
        return cls(waypoints)
    
    @classmethod
    def grid(
        cls,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        rows: int = 5,
        cols: int = 5,
        altitude_m: float = 100.0,
        fov_deg: float = 60.0,
    ) -> "FlightPath":
        """Generate a grid survey pattern."""
        waypoints = []
        lats = np.linspace(min_lat, max_lat, rows)
        lons = np.linspace(min_lon, max_lon, cols)
        
        t = 0
        for i, lat in enumerate(lats):
            lon_order = lons if i % 2 == 0 else lons[::-1]
            heading = 90 if i % 2 == 0 else 270
            
            for lon in lon_order:
                waypoints.append(DroneState(
                    lat=lat, lon=lon,
                    altitude_m=altitude_m,
                    heading_deg=heading,
                    fov_deg=fov_deg,
                    timestamp=float(t),
                ))
                t += 1
        
        return cls(waypoints)
    
    @staticmethod
    def state_to_window(state: DroneState, geo: GeoTransform) -> WindowParams:
        """Convert drone state to pixel window parameters."""
        cx, cy = geo.latlon_to_pixel(state.lat, state.lon)
        w, h = geo.fov_to_pixels(state.altitude_m, state.fov_deg)
        return WindowParams(x=cx - w // 2, y=cy - h // 2, width=w, height=h)
    
    def compute_windows(self, geo: GeoTransform) -> List[WindowParams]:
        """Compute all windows for this flight path."""
        return [self.state_to_window(state, geo) for state in self.waypoints]


def simulate_flight(
    loader: FastGeoMap,
    path: FlightPath,
    callback=None,
) -> List[np.ndarray]:
    """
    Simulate a drone flight, extracting windows at each waypoint.
    
    Args:
        loader: FastGeoMap instance
        path: Flight path
        callback: Optional callback(state, window_data) for each frame
        
    Returns:
        List of window arrays (copies, not views)
    """
    geo = GeoTransform(loader.meta.transform)
    windows = path.compute_windows(geo)
    
    results = []
    for state, win in zip(path, windows):
        if not win.is_valid(loader.width, loader.height):
            results.append(None)
            continue
        
        data = loader.get_window_copy(win.x, win.y, win.width, win.height)
        results.append(data)
        
        if callback:
            callback(state, data)
    
    return results
