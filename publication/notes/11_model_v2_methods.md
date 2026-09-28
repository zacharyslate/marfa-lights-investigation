# 11. Line-of-sight model v2: methods, verification and robustness (status 2026-09-28)

This note records the rebuilt line-of-sight model (code in `analysis/marfa/`, tests in `analysis/tests/`). It replaces the browser engine (`analysis/los_browser.js`) as the source of truth. Every number below comes from files in `data/derived/los2/`.

## 1. Data (all pinned in `data/dem/MANIFEST.json`: URL, bytes, SHA-256, Last-Modified)

| Layer | Product | Use |
|---|---|---|
| Terrain, primary | USGS 3DEP 1 m DEM, lidar project TX_WestTexas_2018_D19, 27 tiles (10 km), QL2, flown Feb–May 2019 (Optech Galaxy; Merrick-Surdex JV) | every sample inside the tiles |
| Terrain, fallback | USGS 3DEP 1/3″ (4 tiles) then 1″ (6 tiles), current editions (30 Aug 2022) | outside the lidar tiles |
| Lidar accuracy | USGS check-point test: non-vegetated RMSEz 5.6 cm (565 pts); vegetated 95th pct 21.6 cm (461 pts) (`data/dem/lidar_accuracy.txt`) | error model |
| Obstructions | Same lidar, point cloud (EPT copies of work units B3 and B7 on AWS), 894 octree nodes, 29.4 M points around the grazing corridors (`data/dem/ept_nodes.json`) | shrubs, trees, structures |
| Geoid | NOAA GEOID12B (the model the lidar heights were produced with); GEOID18 as sensitivity (differs by −0.06…+0.06 m over the area) | NAVD88 → ellipsoidal heights |
| Roads | TxDOT Roadways (EXT_DATE 2026-09-01), all 821 public-road features in the area (`data/inputs/txdot_roadways_bigbend.geojson`) | targets |

The author's hand-traced US-67 line differs from TxDOT's centreline by 2.0 m median, 4.9 m at the 90th percentile and 9.3 m at most.

## 2. Geometry

- The eye, the lamp and every terrain sample are placed in Earth-centred (ECEF) coordinates on the WGS84 ellipsoid, with h = H(NAVD88) + N(GEOID12B).
- Each terrain sample's height y_i is measured perpendicular to the straight eye–lamp chord, in the vertical plane. Earth curvature therefore enters exactly; no d²/2R approximation is used.
- Horizontal paths are WGS84 geodesics (Karney, via pyproj).
- Constant-k refraction adds a sag k·s(D−s)/2R above the chord, where R is the normal-section radius (Euler).
- The lamp is visible when k ≥ k_crit = max_i 2R·y_i / (s_i(D−s_i)).
- Sampling is every 2 m within 3 km of either end and every 5 m in between. The first 5 m at the eye and the last 3 m at the car are skipped (the car body).
- **Viewer:** the lidar resolves the viewing platform as a pad 1.3–1.5 m above the surrounding ground. The ground height is 1494.80 m NAVD88 and the eye 1.6 m above that. The old 1″ DEM put the ground at 1493.57 m, which made the eye about 1.2 m too low.

## 3. Robustness metrics (new)

1. **Lamp margin dL and eye margin dE.** The smallest change in lamp height (or eye height) that flips visibility. Tests verify that moving the lamp or eye by exactly this amount puts the ray on the terrain.
2. **Terrain Monte Carlo** (200 draws per point):
   - correlated Gaussian terrain errors per DEM source:
     - lidar: σ 0.056 m, correlation length 20 m;
     - 1/3″: σ 0.56 m, correlation length 70 m;
     - 1″: σ 2.05 m, correlation length 125 m;
   - an eye-height error of σ 0.15 m.

   The 1/3″ and 1″ values were measured against the lidar on 40,000 points and 300 transects (`dem_error.json`). The output is P_vis, from which each point is classed as robustly visible (P ≥ 0.95), robustly hidden (P ≤ 0.05) or uncertain.
3. **Obstructions.** Heights above bare earth come from the point cloud on the DEM's 1 m grid:
   - 'dense' (reference): at least 2 returns and at least 25% of returns more than 0.3 m above ground;
   - 'max' (upper bound): any return.

   Check of the point cloud against the DEM: 2.8 M ground returns differ from it by a median of −0.8 mm, with a robust SD of 2 cm.
4. **Uniform clutter bound.** 0.25, 0.5 and 1 m added to all terrain more than 10 m from both ends.
5. **Height-dependent refraction.** A ray tracer solves y'' = −k(a)/R through temperature profiles that follow the terrain (see §6).

## 4. Verification

- **22 unit tests pass**, including:
  - Euler radius;
  - smooth-Earth horizon distances for k = 0, 0.13 and 0.5;
  - k_crit against brute force on random terrain;
  - an isolated ridge;
  - the margins flipping visibility;
  - AR(1) error statistics;
  - deterministic Monte Carlo;
  - Monte Carlo against the analytic eye-error probability;
  - the ray tracer reproducing constant k;
  - the ray tracer's surface-duct reach matching the analytic value.
- **Old engine reproduced.** Run with the old settings (1″ DEM, 15 m step, 30/60 m exclusions) on the old points, the new engine agrees on visibility for 1075 of 1077 points. The old "clearance" equals the new lamp margin to −0.03 m median (−0.60 to +0.15 m, 5th–95th percentile). The old azimuths were 0.117° too high on average (0.145° at most) and distances were off by up to 72 m, both from the spherical/ellipsoidal mix. The old visibility results were essentially right; their error was in plotted positions.
- **Convergence.** A 1 m / 2 m step against 2 m / 5 m gives identical visibility (3095/3095). Near-car exclusion of 3, 30 and 60 m gives 10.44, 10.47 and 10.59 km. Only 120 m (11.19 km) departs, because it discards real terrain.

## 5. Results for US-67 (3095 points every 30 m from the US-90 junction in Marfa toward Presidio; 0.66 m headlamp, k = 0.13, unless stated)

| Configuration | Visible (km) | Monte Carlo: robust visible / uncertain (km) |
|---|---|---|
| 1″ DEM | 10.26 | 0.00 / 9.81 |
| 1/3″ DEM | 10.26 | 0.21 / 10.71 |
| Lidar, bare earth | 10.44 | 10.26 / 0.21 |
| **Lidar + point-cloud obstructions (reference)** | **9.93** | **9.72 / 0.27** |
| Lidar + obstructions ('max' bound) | 9.84 | — |
| Reference + 0.25 m uniform grass (below lidar detection) | 9.36 | — |
| Reference + 1 m uniform clutter (unrealistic bound) | 2.04 | — |

- **DEM resolution.** The three DEMs agree deterministically (98.6–99.7% of points). But only the lidar is accurate enough to decide visibility robustly, because the rays graze within about 1 m of the ground over long stretches: every visible point has a lamp margin under 2 m.
- **Obstructions.** Measured vegetation and structures remove about 0.5 km, because the ground is open grassland (0.8% of corridor cells carry dense cover above 0.3 m).
- **Where the light is stopped.** The limiting terrain sample lies a median 3.0 km from the car; it is within 100 m of the car for only 9% of points. The old 1/3″ model's "first sample after the exclusion" artefact (referee point C1) is gone.
- **Where US-67 is visible.** About 29 separate stretches between 18.1 and 35.5 km along the road from Marfa, at 18–40 km from the platform, azimuth 229–252°, apparent elevation −0.40° to +0.06°.
- **Visible length by lamp height and k (reference run):**

  | Lamp | k = 0 | k = 0.13 | k = 1 |
  |---|---|---|---|
  | 0.56 m | 9.45 km | 9.72 km | 11.49 km |
  | 1.37 m | 10.59 km | 10.83 km | 12.42 km |
  | 4.0 m (truck clearance lamps) | 13.50 km | 13.77 km | 15.33 km |

## 6. Height-dependent refraction (`data/derived/los2/trace_us67.npz`)

- **Relation used:** k = 503·P/T²·(0.0343 + dT/dz) (Hirt et al. 2010, JGR 115, D21102, eq. 2), with P = 850 hPa and T = 283 K. Hirt et al. measured k from −4 to +16 at 1.8 m over grass, with gradients up to 1–2 K/m after sunset. A single k between 0 and 1 is therefore not an adequate description near the ground at night.
- **Scenarios:**
  - exponential stable boundary layer: weak (3 K over 50 m), moderate (6 K over 30 m), strong (10 K over 20 m);
  - isothermal;
  - neutral;
  - an elevated inversion (4 K between 40 and 60 m).

  These are brackets, not a climatology.
- **Which points were traced.** The largest local k in any scenario is 2.82. The constant-k_max arc bounds every ray from above (y'' ≥ −k_max/R with fixed end points), so points with k_crit > 2.9 are provably hidden. The remaining 212 points (60 m spacing) were traced.

| Scenario | Visible (km) | Median k_equiv | Lift over k = 0.13 (median / max) |
|---|---|---|---|
| neutral | 9.78 (reproduces constant k) | 0.13 | 0 |
| isothermal | 9.90 | 0.18 | 0.4′ / 0.6′ |
| SBL weak | 10.86 | 0.30 | 1.4′ / 1.7′ |
| SBL moderate | 10.92 | 0.47 | 2.9′ / 4.3′ |
| SBL strong | 11.28 | 0.67 | 4.5′ / 7.5′ |
| Elevated inversion 40–60 m | 9.66 | 0.36 | 1.8′ / 2.8′ |

- **Multiple images.** The elevated inversion gives 3–5 images of one lamp on about 0.3 km of road (points 18.6–24.4 km from Marfa). They are stable when the step drops from 5 m to 1 m and the fan density rises sevenfold, but they are only 1–8 arcsec apart. That is below naked-eye resolution: an observer would see one light, possibly scintillating, not a cluster. Do not claim visible "splitting" from this model.
- **Why no multiple images in the surface layers.** A surface layer whose gradient decreases monotonically with height produced single images only.

## 7. What is still open (next steps, in order)

1. **Port the other generators** to the new engine: all TxDOT roads at 60 m, rail (1.2/4 m lamps), towers, towns, skyline/panorama, profiles. Then retire `los_browser.js` and the old derived files.
2. **Photometry.**
   - Wide-angle intensity: at 68% of geometries the viewer is outside the measured beam of the one production headlamp in the model.
   - Add DRLs, position, marker, tail and stop lamps with the FMVSS 108 limits (verify the table values before citing).
   - Model the detection limit with horizon sky brightness and extinction.
   - Model occupancy as flow × dwell time.
3. **Redo the photo validation without circularity:**
   - calibrate pointing with stars (plate solving);
   - use a pre-registered threshold;
   - measure distances to the road polyline;
   - fix the note 09 errors (the scale sign; f ≈ 204 mm; 0.057⁶ vs 0.057¹²; the p09 duplicate; p13's ±60 px window; the p04/p10 and p09→p10 motion inconsistencies).
4. **Experimental section (field):**
   - GNSS survey of the platform eye point;
   - temperature mast at 0.5, 2, 5, 10 m (plus tethered or drone profiles) to measure k(z, t);
   - time series of the apparent elevation of fixed distant lights;
   - controlled GNSS-tracked vehicle runs on US-67 with blind observers, scored by Brier score or ROC;
   - two-station triangulation;
   - traffic counts and ADS-B logs;
   - pre-registration.
5. **Update every figure from `los2`, then write the manuscript.** Target journal still to be chosen by the author.
