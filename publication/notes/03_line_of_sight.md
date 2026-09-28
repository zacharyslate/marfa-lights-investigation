# 3. Line of sight and the critical refraction coefficient

## Terrain model

- USGS 3D Elevation Program (3DEP), `3DEPElevation` ImageServer, retrieved 28 Sep 2026.
- 1 arc-second (≈30 m) grid over −104.62…−103.86° E, 29.72…30.40° N.
- 3 arc-second grid over −105.45…−103.00° E, 29.10…30.95° N, used wherever the 1″ grid does not reach.
- Bilinear interpolation between grid points.
- The DEM is bare-earth: brush, buildings, road cuts and embankments are not represented.

## Visibility test

Setup:
- The eye is at elevation *E* = *z₀* + 1.6 m.
- A target lamp is at height *h* above ground *z_t*, at distance *d_t*.
- Terrain samples *z_i* lie at distances *d_i* along the geodesic: every 15 m for US-67 targets, every 30–60 m for other targets.
- Samples within the first 30 m and the last 60 m are skipped. This avoids the observer's own pad and the road shoulder.

Correct each height for curvature and refraction, and take the tangent of its elevation angle:

    θ_i = [z_i − E − d_i²(1 − k)/(2R)] / d_i
    θ_t = [z_t + h − E − d_t²(1 − k)/(2R)] / d_t

The target is visible if θ_t ≥ max_i θ_i. The **clearance** (θ_t − max θ_i)·d_t is how far, in metres, the lamp sits above (+) or below (−) the limiting sight line.

## Critical refraction coefficient

Write *c* = 1 − *k*. The condition θ_t ≥ θ_i rearranges to a bound on *c* for each sample:

    c ≤ 2R [ (z_t + h − E)/d_t − (z_i − E)/d_i ] / (d_t − d_i)

So the lamp is visible exactly when

    k ≥ k_crit = 1 − min_i { 2R [ (z_t + h − E)/d_t − (z_i − E)/d_i ] / (d_t − d_i) }

One pass over the profile gives *k_crit*. After that, visibility at any refraction is a single comparison, k ≥ k_crit. The website's refraction slider and **Figure 5a** both work this way. Values of k_crit below 0 mean the lamp is visible even with less bending than standard. Values above about 1 require an unusually strong inversion.

## Visibility classes for US-67

The classes are defined at k = 0.13, for a 0.7 m lamp.

| Class | Rule | Length of US-67 |
|---|---|---|
| visible | k_crit ≤ 0.13 and clearance > 5 m, where clearance ignores the last 1 km before the car | 9.3 km |
| marginal | the lamp just grazes the terrain (clearance ≤ 5 m), or it is blocked only within 1 km of the car, where road cuts and brush the DEM cannot see decide the answer | 7.4 km |
| hidden | everything else | 47.9 km |

All visible US-67 lies at 228.8°–238.2° true, 24–40 km from the Viewing Area. The other state roads (TxDOT) use the simpler rule k_crit ≤ 0.13 at 120 m spacing. On that rule, 27.4 km of **RM 2810** is in view, at 252.9°–259.1° true and 32–53 km away.

## Cross-sections (Figure 4)

Figure 4 plots *y(d) = z(d) − E − d²(1−k)/(2R)* against *d*. In these coordinates every sight line from the eye is a straight line through the origin. Terrain is in view where it rises above every earlier ray; this is the running maximum of *y/d*. The steepest ray marks the skyline.

## Skyline and ridge layers (panorama)

- For each true bearing from 140° to 300°, every 0.1°: the maximum of θ over 60 m samples out to the edge of the DEM (≤ 160 km). This gives the skyline angle and its distance.
- The same maximum restricted to the first 10, 25 and 45 km gives the nested ridge silhouettes in Figure 2.
- In 19 of the 1,601 bearings the skyline lies 100 km or more away. There the skyline may be slightly too low, because terrain beyond the DEM edge is not included.

## Limitations

1. The DEM is bare-earth at about 30 m. Road cuts, fills, brush and structures can hide or reveal a lamp by a few metres. The marginal class exists to flag exactly these cases.
2. Refraction is a single *k* per path (see note 2).
3. The observer point came from a hand-placed Google Earth pin. Moving along the viewing platform by a few tens of metres can change near-grazing results.
4. There has been no field check yet. The first field task should be to confirm the predicted visible US-67 segments with a car of known position.

## Code

- `analysis/los_browser.js`: the line-of-sight engine. It is run in a browser against the USGS service, because the analysis environment could not reach USGS directly.
- Outputs are in `data/derived/los_results.json`, `los_near_far.json`, `panorama_los.json`, `roads_los.json` and `profiles_fig.json`.
