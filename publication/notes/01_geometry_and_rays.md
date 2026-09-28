# 1. Geometry: the viewing fan and the rays

## Observer

| Quantity | Value | Source |
|---|---|---|
| Viewing Area position | 30.2751108° N, 103.8827973° W | point in `data/inputs/Investigation_Marfa.kml` (Google Earth trace by the author) |
| Ground elevation | 1,493.6 m | USGS 3DEP 1 arc-second DEM, bilinear |
| Eye height | 1.6 m above ground | assumption (standing adult) |
| Magnetic declination | 6.2° E, changing about −0.08° per year | NOAA World Magnetic Model WMM2025, epoch 2026.7 |

All bearings in this project are **true** (clockwise from geographic north). A magnetic compass reads 6.2° less than the true bearing, so true = magnetic + 6.2°.

## The fan

The fan is bounded on the right by the author's original "Right Line" (277.276° true). The left bound was widened twice: first from the US-67 high point (228.9°) to the Shafter end of the highway trace (218.985°), and now (28 Sep 2026) to **157.276° true**, exactly 120° anticlockwise of the right bound. Rays are cast every 0.5°, which gives **241 rays**.

- Rays between 218.985° and 277.276° end at their first crossing of US-67.
- The 124 rays from 157.3° to 218.5° never meet US-67. They are drawn to 80 km, and they cover Mitchell Flat to the south and south-southwest, where the Texas Pacifico railroad runs.

## Geodesics

Azimuths and distances are geodesics on the WGS84 ellipsoid, computed with `pyproj.Geod` (Karney's algorithms; Karney 2013). To intersect rays with the highway, both are projected into an azimuthal-equidistant (AEQD) projection centred on the observer. In that projection every line through the centre is an exact geodesic and every distance from the centre is exact, so a ray is a straight segment and the intersection is a plain planar computation (`shapely`).

## Angular size at range: a rule of thumb

At distance *d*, an angle θ (in radians) spans a width *w* = *d*θ:

| *d* | 0.1° spans | 1 m spans |
|---|---|---|
| 10 km | 17 m | 0.10 mrad (0.006°) |
| 30 km | 52 m | 0.033 mrad (0.002°) |
| 50 km | 87 m | 0.020 mrad (0.001°) |

Two headlamps about 1.4 m apart at 30 km are 0.05 mrad apart. That is far below the eye's resolution of roughly 0.3 mrad (1 arcminute), so a car at that range looks like a single point. This is why the brightness model adds the two lamps together (note 4).

## Files

- `analysis/marfa_ray_fan.py`: the fan, the intersections, and the 30 m profile sample points.
  - Constants: `FAN_SPAN_DEG = 120`, `STEP_DEG = 0.5`, `NOHIT_LEN_M = 80 km`.
- `outputs/Marfa_ray_fan.kml`: the fan for Google Earth.
- `outputs/Marfa_ray_fan_hits.csv`: one row per ray and highway crossing.

## References

- Karney, C. F. F. (2013). Algorithms for geodesics. *Journal of Geodesy* 87, 43–55. doi:10.1007/s00190-012-0578-z
- NOAA NCEI, World Magnetic Model 2025. https://www.ncei.noaa.gov/products/world-magnetic-model
