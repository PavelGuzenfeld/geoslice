"""Contract tests for FlightPath, WindowParams and simulate_flight.

Adopting the mutation gate measured a 14% kill rate on drone.py: 42 of 49
mutants survived. These pin the behaviour each function's name, signature and
docstring already promise.

They deliberately do NOT pin what the model spec (issue #6) flags as
needing intent — the radius units of MS-8. A test
written against what the code currently computes there would freeze a
simplification nobody has confirmed, which is the opposite of useful.
"""

import math

import numpy as np
import pytest

from geoslice import DroneState, FlightPath
from geoslice.drone import WindowParams, simulate_flight


class TestWindowValidity:
    """is_valid(map_width, map_height) asks whether the window lies inside the
    map. Every assertion here sits on a boundary, because that is where `<`
    versus `<=` and `>` versus `>=` become observable."""

    def test_a_window_flush_with_the_origin_is_inside_the_map(self):
        assert WindowParams(x=0, y=0, width=10, height=10).is_valid(100, 100)

    def test_a_window_one_pixel_left_of_the_origin_is_outside(self):
        assert not WindowParams(x=-1, y=0, width=10, height=10).is_valid(100, 100)

    def test_a_window_one_pixel_above_the_origin_is_outside(self):
        assert not WindowParams(x=0, y=-1, width=10, height=10).is_valid(100, 100)

    def test_a_window_ending_exactly_on_the_right_edge_is_inside(self):
        assert WindowParams(x=90, y=0, width=10, height=10).is_valid(100, 100)

    def test_a_window_ending_one_pixel_past_the_right_edge_is_outside(self):
        assert not WindowParams(x=91, y=0, width=10, height=10).is_valid(100, 100)

    def test_a_window_ending_exactly_on_the_bottom_edge_is_inside(self):
        assert WindowParams(x=0, y=90, width=10, height=10).is_valid(100, 100)

    def test_a_window_ending_one_pixel_past_the_bottom_edge_is_outside(self):
        assert not WindowParams(x=0, y=91, width=10, height=10).is_valid(100, 100)


class TestDroneStateDefaults:
    """The defaults are public API — a caller that omits them gets these."""

    def test_a_state_given_only_a_position_faces_north_and_is_stationary_at_time_zero(self):
        state = DroneState(lat=1.0, lon=2.0, altitude_m=100.0)
        assert state.heading_deg == 0.0
        assert state.speed_ms == 0.0
        assert state.timestamp == 0.0

    def test_the_default_field_of_view_is_sixty_degrees(self):
        assert DroneState(lat=1.0, lon=2.0, altitude_m=100.0).fov_deg == 60.0


class TestSpiral:
    """Anchored on the docstring — "a spiral flight path around a center point".
    No test here cites MS-8: that line is tagged (needs intent) and was itself
    reconstructed from this code, so citing it would assert the code against
    itself. The units of radius_deg stay unasserted for the same reason."""

    def test_it_returns_the_requested_number_of_waypoints(self):
        assert len(FlightPath.spiral(0.0, 0.0, num_waypoints=7)) == 7

    def test_the_arm_grows_outward_rather_than_collapsing_inward(self):
        # A path that spirals inward with i is not "a spiral around a centre".
        path = FlightPath.spiral(0.0, 0.0, num_waypoints=6, radius_deg=0.01)
        radii = [np.hypot(w.lat, w.lon) for w in path]
        assert radii == sorted(radii)
        assert radii[0] < radii[-1]

    def test_the_first_waypoint_sits_one_radius_step_out_not_on_the_centre(self):
        # "Around a centre point": a waypoint at radius 0 is on it, not around it.
        path = FlightPath.spiral(10.0, 20.0, num_waypoints=3, radius_deg=0.25)
        offset = np.hypot(path[0].lat - 10.0, path[0].lon - 20.0)
        # Tolerance is one cos/sin round trip on a 0.25 magnitude: the radius is
        # decomposed into components and recombined, nothing accumulates.
        assert offset == pytest.approx(0.25, abs=1e-15)

    def test_each_waypoint_heads_along_the_leg_to_the_next_not_away_from_the_centre(self):
        """MS-17 with the MS-7 bearing over (70, 0), (60, 20), (30, 0), (60, -40); the last repeats.
        Tolerance: cos(90 deg) and sin(180 deg) leave ~1e-14 deg in the positions, not exact 0."""
        path = FlightPath.spiral(60.0, 0.0, num_waypoints=4, radius_deg=10.0)
        into_last = math.degrees(math.atan2(-40 * math.cos(math.radians(45)), 30))
        expected = [
            math.degrees(math.atan2(20 * math.cos(math.radians(65)), -10)),
            math.degrees(math.atan2(-20 * math.cos(math.radians(45)), -30)),
            into_last,
            into_last,
        ]
        assert [w.heading_deg for w in path] == pytest.approx(
            [e % 360 for e in expected], abs=1e-12
        )

    def test_a_lone_waypoint_has_no_leg_and_heads_zero(self):
        """MS-17: a one-waypoint spiral has no leg and heads 0."""
        path = FlightPath.spiral(10.0, 20.0, num_waypoints=1, radius_deg=0.5)
        assert [w.heading_deg for w in path] == [0.0]

    def test_altitudes_cycle_through_the_given_list(self):
        path = FlightPath.spiral(0.0, 0.0, num_waypoints=5, altitudes=[10.0, 20.0])
        assert [w.altitude_m for w in path] == [10.0, 20.0, 10.0, 20.0, 10.0]

    def test_timestamps_count_the_waypoints_from_zero(self):
        path = FlightPath.spiral(0.0, 0.0, num_waypoints=4)
        assert [w.timestamp for w in path] == [0.0, 1.0, 2.0, 3.0]


class TestLinear:
    """A straight run between two points. Due north and due south have one heading
    under any bearing definition; off-axis legs count a degree of longitude by cos(lat)."""

    def test_a_leg_due_north_heads_zero_not_east(self):
        """MS-18: a northbound meridian leg heads 0."""
        path = FlightPath.linear(32.0, 34.0, 33.0, 34.0, num_waypoints=3)
        assert [w.heading_deg for w in path] == [0.0, 0.0, 0.0]

    def test_a_leg_due_south_heads_one_eighty_not_back_north(self):
        """MS-18: a southbound meridian leg heads 180."""
        path = FlightPath.linear(33.0, 34.0, 32.0, 34.0, num_waypoints=3)
        assert [w.heading_deg for w in path] == [180.0, 180.0, 180.0]

    def test_a_leg_at_sixty_north_counts_a_degree_of_longitude_as_half_a_degree(self):
        """MS-7: at mean latitude 60, 2 degrees east and 1 north is a 45 degree ground bearing.
        Tolerance: cos(60 deg) rounds to 0.5000000000000001, moving the bearing ~7e-15 deg."""
        path = FlightPath.linear(59.5, 34.0, 60.5, 36.0, num_waypoints=3)
        assert [w.heading_deg for w in path] == pytest.approx([45.0, 45.0, 45.0], abs=1e-13)

    def test_a_leg_at_sixty_north_heading_south_west_turns_225_clockwise_not_45(self):
        """MS-7: the reverse of the 45 degree leg heads 225 clockwise from north.
        Tolerance: the same cos(60 deg) rounding."""
        path = FlightPath.linear(60.5, 36.0, 59.5, 34.0, num_waypoints=3)
        assert [w.heading_deg for w in path] == pytest.approx([225.0] * 3, abs=1e-13)

    def test_a_leg_due_west_heads_270_not_minus_90(self):
        """MS-7: heading_deg lies in [0, 360), so a westbound leg along a parallel heads 270."""
        path = FlightPath.linear(32.0, 35.0, 32.0, 34.0, num_waypoints=3)
        assert [w.heading_deg for w in path] == [270.0, 270.0, 270.0]

    def test_a_leg_a_hair_west_of_north_heads_zero_not_360(self):
        """MS-7: a bearing within rounding of 360 wraps to 0, keeping heading_deg inside [0, 360)."""
        path = FlightPath.linear(0.0, 0.0, 1.0, -1e-16, num_waypoints=3)
        assert [w.heading_deg for w in path] == [0.0, 0.0, 0.0]

    def test_it_starts_at_the_start_and_ends_at_the_end(self):
        # No tolerance: np.linspace pins both endpoints exactly, verified.
        path = FlightPath.linear(1.0, 2.0, 3.0, 4.0, num_waypoints=5)
        assert (path[0].lat, path[0].lon) == (1.0, 2.0)
        assert (path[-1].lat, path[-1].lon) == (3.0, 4.0)

    def test_it_returns_the_requested_number_of_waypoints(self):
        assert len(FlightPath.linear(0.0, 0.0, 1.0, 1.0, num_waypoints=9)) == 9

    def test_every_waypoint_shares_one_heading_because_the_run_is_straight(self):
        path = FlightPath.linear(0.0, 0.0, 1.0, 1.0, num_waypoints=5)
        assert len({w.heading_deg for w in path}) == 1

    def test_waypoints_are_evenly_spaced_along_the_run(self):
        # Exactly representable at this step: 4/4 is 1.0, so no tolerance is owed.
        path = FlightPath.linear(0.0, 0.0, 4.0, 0.0, num_waypoints=5)
        assert [w.lat for w in path] == [0.0, 1.0, 2.0, 3.0, 4.0]


class TestGrid:
    """A survey pattern: the rows are walked in alternating directions so the
    drone does not fly back across the area empty between passes."""

    def test_it_returns_one_waypoint_per_cell(self):
        assert len(FlightPath.grid(0.0, 0.0, 1.0, 1.0, rows=3, cols=4)) == 12

    def test_consecutive_rows_are_walked_in_opposite_directions(self):
        # Four rows, not two: with two, `i % 2` and `i % 3` agree on every row
        # and a mutated modulus is invisible. The third row is what separates them.
        path = FlightPath.grid(0.0, 0.0, 3.0, 3.0, rows=4, cols=4)
        rows = [[w.lon for w in path[n * 4 : (n + 1) * 4]] for n in range(4)]
        assert rows[0] == sorted(rows[0])
        assert rows[1] == sorted(rows[1], reverse=True)
        assert rows[2] == sorted(rows[2])
        assert rows[3] == sorted(rows[3], reverse=True)

    def test_the_heading_reverses_with_the_direction_of_travel(self):
        path = FlightPath.grid(0.0, 0.0, 1.0, 1.0, rows=2, cols=2)
        assert {w.heading_deg for w in path[:2]} == {90}
        assert {w.heading_deg for w in path[2:]} == {270}

    def test_timestamps_run_unbroken_across_the_row_turn(self):
        path = FlightPath.grid(0.0, 0.0, 1.0, 1.0, rows=2, cols=3)
        assert [w.timestamp for w in path] == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


class TestDefaults:
    """A caller who passes nothing gets these. They are public API, so they are
    pinned here — which is not a claim that any of the values is geodetically
    right. MS-8 still flags what radius_deg even means."""

    def test_spiral_defaults(self):
        path = FlightPath.spiral(0.0, 0.0)
        assert len(path) == 20
        assert path[0].fov_deg == 60.0
        assert np.hypot(path[0].lat, path[0].lon) == pytest.approx(0.001, abs=1e-15)
        assert [w.altitude_m for w in path][:5] == [50, 100, 150, 200, 250]

    def test_linear_defaults(self):
        path = FlightPath.linear(0.0, 0.0, 1.0, 1.0)
        assert len(path) == 20
        assert path[0].altitude_m == 100.0
        assert path[0].fov_deg == 60.0

    def test_grid_defaults(self):
        path = FlightPath.grid(0.0, 0.0, 1.0, 1.0)
        assert len(path) == 25  # 5 rows x 5 cols
        assert path[0].altitude_m == 100.0
        assert path[0].fov_deg == 60.0


class _Geo:
    """A GeoTransform stand-in: fixed pixel centre and window size, so the window
    arithmetic is observable without a raster."""

    def __init__(self, centre=(100, 200), size=(10, 20)):
        self._centre, self._size = centre, size

    def latlon_to_pixel(self, lat, lon):
        return self._centre

    def fov_to_pixels(self, altitude_m, fov_deg):
        return self._size


class TestStateToWindow:
    def test_the_window_is_centred_on_the_pixel_the_state_maps_to(self):
        win = FlightPath.state_to_window(
            DroneState(lat=0.0, lon=0.0, altitude_m=100.0), _Geo()
        )
        assert win.x + win.width // 2 == 100
        assert win.y + win.height // 2 == 200

    def test_the_window_takes_its_size_from_the_field_of_view(self):
        win = FlightPath.state_to_window(
            DroneState(lat=0.0, lon=0.0, altitude_m=100.0), _Geo(size=(10, 20))
        )
        assert (win.width, win.height) == (10, 20)


class _Loader:
    """A FastGeoMap stand-in recording which windows were actually read."""

    def __init__(self, width=1000, height=1000):
        self.width, self.height = width, height
        self.reads: list[tuple] = []
        self.meta = type("Meta", (), {"transform": (1.0, 0, 0, 0, 1.0, 0)})()

    def get_window_copy(self, x, y, w, h):
        self.reads.append((x, y, w, h))
        return np.zeros((h, w))


def _path_of(n: int) -> FlightPath:
    return FlightPath([DroneState(lat=0.0, lon=0.0, altitude_m=100.0) for _ in range(n)])


class TestSimulateFlight:
    """The docstring promises one entry per waypoint. An out-of-bounds window
    yields None for that waypoint and the flight carries on."""

    def test_an_out_of_bounds_waypoint_does_not_truncate_the_rest_of_the_flight(
        self, monkeypatch
    ):
        loader = _Loader()
        windows = [
            WindowParams(0, 0, 10, 10),
            WindowParams(-5, 0, 10, 10),  # outside
            WindowParams(20, 20, 10, 10),
        ]
        monkeypatch.setattr(FlightPath, "compute_windows", lambda self, geo: windows)

        results = simulate_flight(loader, _path_of(3))

        assert len(results) == 3
        assert results[1] is None
        assert results[0] is not None and results[2] is not None

    def test_an_out_of_bounds_window_is_never_read_from_the_map(self, monkeypatch):
        loader = _Loader()
        monkeypatch.setattr(
            FlightPath, "compute_windows", lambda self, geo: [WindowParams(-5, 0, 10, 10)]
        )

        assert simulate_flight(loader, _path_of(1)) == [None]
        assert loader.reads == []

    def test_the_callback_fires_once_per_window_actually_read(self, monkeypatch):
        loader = _Loader()
        windows = [WindowParams(0, 0, 10, 10), WindowParams(-5, 0, 10, 10)]
        monkeypatch.setattr(FlightPath, "compute_windows", lambda self, geo: windows)
        seen = []

        simulate_flight(loader, _path_of(2), callback=lambda s, d: seen.append(d))

        assert len(seen) == 1
