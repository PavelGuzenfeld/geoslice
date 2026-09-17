# geoslice model spec

Reconstructed from the implementation on 2026-09-17 so the mutation gate has a
Layer 0 to check against. **Every line below is tagged.** `(reconstructed)` means
it was read out of the code and is true of what the code does today.
`(needs intent)` means the code does not say it and nobody has written it down —
those are the lines that decide whether the code is right, and a spec derived
from the implementation can only agree with the implementation.

Do not treat an untagged-looking line as agreed. Nothing here has been checked
against a requirement yet.

## Phenomena modelled

MS-1. Geodetic latitude/longitude on the WGS84 ellipsoid, `a = 6378137.0 m`,
`f = 1/298.257223563`, declared as `GeoTransform._WGS84_A` and `._WGS84_F`.
(reconstructed)

MS-2. Projection to UTM by the standard Transverse Mercator series, scale factor
`_UTM_K0`, central meridian taken from `utm_zone` and defaulting to zone 36.
The meridional arc `M` is the usual series truncated after the `e^6` term.
(reconstructed)

MS-3. Pixel addressing by a 6-element affine transform: `pixel_size_x =
transform[0]`, `pixel_size_y = abs(transform[4])`, origin `transform[2]`,
`transform[5]`. The GeoTIFF convention, north-up, no rotation terms used.
(reconstructed)

MS-4. Camera footprint as `ground_width = 2 * altitude_m * tan(fov_deg / 2)`,
then divided by pixel size on each axis independently. (reconstructed)

MS-5. Waypoint heading as `degrees(atan2(dlon, dlat))` over raw degree
differences. (reconstructed)

## Effects deliberately neglected

Each of these is a real simplification in the code. None carries a justification
in the code, and none has a measured margin — that is what makes them
`(needs intent)` rather than settled.

MS-6. The footprint of MS-4 assumes a nadir-pointing camera over flat ground.
Obliquity, terrain relief and lens distortion are all absent, and the two axes
are computed from one `ground_width`, so a non-square sensor is not modelled.
Whether that holds over the intended terrain is unstated. (needs intent)

MS-7. The heading of MS-5 treats a degree of longitude and a degree of latitude
as the same length. They differ by `cos(lat)`, so the bearing is wrong by roughly
that factor away from the equator — about 20% at 36 degrees north, the default
zone. It is also a planar bearing, not a great-circle initial bearing. Whether a
planar bearing is intended, and over what leg length, is unstated. (needs intent)

MS-8. `FlightPath.circular` builds waypoints as `lat = center_lat + radius *
cos(angle)` and `lon = center_lon + radius * sin(angle)`, with `radius` in
degrees. This carries the same anisotropy as MS-7: the resulting path is an
ellipse on the ground, not a circle. Whether `radius` is meant to be degrees or
metres is unstated. (needs intent)

MS-9. The UTM series of MS-2 is truncated, so it degrades with distance from the
central meridian and fails near the poles. The usable band is unstated.
(needs intent)

MS-10. No datum transformation. Input coordinates are assumed to be WGS84
already. (reconstructed)

## Validity envelope

MS-11. Latitude and longitude range over which MS-2 is required to hold, and the
zone-crossing behaviour when a path leaves `utm_zone`. Unstated; the code neither
checks nor warns. (needs intent)

MS-12. Altitude range for MS-4, and the maximum off-nadir angle before MS-6 stops
being acceptable. Unstated. (needs intent)

MS-13. Leg length over which the planar bearing of MS-5 and MS-7 is acceptable.
Unstated. (needs intent)

## Required accuracy

MS-14. Positional accuracy required of the lat/lon to pixel path, per region of
the envelope. Unstated — there is no tolerance anywhere in the tests, so nothing
currently pins this. (needs intent)

MS-15. Angular accuracy required of MS-5. Unstated. (needs intent)

## Noise assumptions

MS-16. None. There is no estimator, no filter and no noise model in this repo;
every transform is deterministic. If drone state ever arrives from a sensor
rather than from a caller, this section becomes load-bearing and is currently
empty. (reconstructed)

## What to do with this file

The `(reconstructed)` lines can be trusted as a description of today's code. The
`(needs intent)` lines are the ones worth your time: each one is a place where
the code made a choice and nothing records whether the choice was right. Filling
one in either confirms the simplification, with the margin that makes it safe, or
turns it into a bug with a test.

Until then the gate treats this spec as present but incomplete, which is honest —
it is present, and it is incomplete.
