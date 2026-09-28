# 09 · Photo validation of the sight-line model (v2, 2026-09-28)

The line-of-sight model (notes 01–03 and 11) predicts where headlights on US-67 can appear from the Viewing Area. This note tests that prediction against photographs taken from the Viewing Area.

**What changed in v2.** This version replaces the first analysis. It uses the v2 model (exact geometry, lidar terrain, TxDOT road centreline) and corrects errors that a methods review found in v1. Those errors are listed at the end.

## Data

- **Photographer:** Zach Warren, 21 November 2018.
- **Camera:** Sony ILCE-6300 (APS-C, 23.5 mm sensor, 6000 px wide) with an E 55–210 mm lens set to 210 mm. The nominal focal length is 53,617 px, or 936 px per degree.
- **Frames:** ten frames, camera time 19:12:03–19:26:12, exposures 1/25 s to 45 s, exported at 6000 × 3376 px.
- **Clock check:** one sunset frame from the same camera.
- **Files:**
  - Raw files: `data/photos_raw/` (outside git).
  - Results: `data/derived/photos/`.
  - Scripts: `analysis/photo_register.py`, `photo_sun_clock.py`, `photo_validate.py`, `photo_figures.py`.

## 1. Registration

**Method.**
- The sky–land boundary is traced in each frame: red minus blue drops sharply at the skyline.
- A rectilinear camera model is fitted to the modelled skyline (k = 0.13) by robust least squares. It has four parameters: azimuth *A*₀, elevation *E*₀, roll, and a scale on the focal length.

| Frame | Exposure | *A*₀ (° true) | Skyline RMS (°) | Best alternative pointing, RMS (°) | Ratio |
|---|---|---|---|---|---|
| 04 | 1/25 s | 233.65 | 0.010 | 0.028 | 2.7 |
| 05 | 1/25 s | 233.75 | 0.010 | 0.029 | 2.8 |
| 06 | 1/25 s | 234.81 | 0.008 | 0.056 | 7.3 |
| 07 | 1/25 s | 234.79 | 0.008 | 0.055 | 6.8 |
| 08 | 1/15 s | 234.81 | 0.005 | 0.052 | 10.2 |
| 09 | 1.3 s | 234.70 | 0.005 | 0.049 | 9.5 |
| 10 | 1.6 s | 234.63 | 0.005 | 0.045 | 8.8 |
| 11 | 30 s | 234.64 | 0.005 | 0.045 | 9.1 |
| 12 | 40 s | 234.07 | 0.017 | 0.023 | 1.4 |
| 13 | 45 s | 234.07 | 0.017 | 0.024 | 1.4 |

**What the fit shows.**
- **Better fit than v1.** The v2 skyline fits every frame slightly better than v1 did (for example 0.0049° against 0.0058° in frame 11).
- **Azimuth shift.** Every fitted azimuth moved by +0.12° from v1. That is the size of the azimuth error in the v1 model, which the v1 registration had silently absorbed.
- **Focal length.** The fitted scale is 0.974–0.977 in every frame, so the lens's effective focal length is about 205 mm rather than the nominal 210 mm. (v1 attributed this to an image enlargement by the lens profile. That had the sign wrong: an enlargement would give a scale above 1.)
- **Frames 12–13.** The skyline alone discriminates only weakly in these two frames (ratio 1.4).

**Limitation that remains.** No stars are recorded: the 30–45 s frames were taken in late twilight and the sky near the horizon is saturated. The pointing is therefore fitted to the modelled skyline itself. What follows tests the *internal consistency* of terrain, road geometry, refraction and camera model against real lights. It does not test the absolute pointing; that requires the star-calibrated camera of experiment E1 (note 12).

## 2. Camera clock

The sunset frame registers to the skyline with an RMS of 0.003°. Matching the measured solar disc to the Sun's computed position (Astronomy Engine, with standard refraction) puts the camera clock 59 min ahead of CST. The camera was probably still on daylight time after the 4 November 2018 changeover. The car frames were therefore taken at 18:12–18:26 CST, about 20–35 min after sunset.

## 3. Point lights in the short exposures (frames 04–10)

**Detection.**
- A high-pass image is made by subtracting a 21 × 21 px median.
- A detection must exceed 7 robust standard deviations and have an area of 4–600 px.
- It must lie between the modelled 10 km ridge line and the skyline. Anything more than 10 km away must appear above that ridge line.
- A contrast rule (peak/median ≥ 1.20) was set in v1 after looking at the detections. v2 reports the test both with and without it, and the result is the same.

**Unit of analysis.** Frames taken seconds apart show the same vehicles, so the unit is an independent sighting within a burst of frames: 04+05, 06+07, 08, 09 and 10. Two detections in one burst count as the same vehicle when both hold:
- they lie on the same road;
- their along-road separation is within what a vehicle at 45 m/s or less covers between the frames, plus 60 m.

Duplicate detections within a single frame (less than 0.02° apart) are merged. This gives **8 independent sightings**.

**Statistic.** The angular distance from each sighting to the modelled *curve* of visible road: US-67 and the other state roads, piecewise-linear between the 60 m samples, and only between consecutive in-view samples. The median over the 8 sightings is the test statistic, so there is no post-hoc distance threshold.

**Null model.** The same number of random positions per burst, drawn uniformly in each frame's ground band.

| Quantity | Value |
|---|---|
| Median distance of the 8 sightings from visible road | **0.0085°** (7.7 px; about 4 m at 26 km) |
| Largest distance | 0.013° |
| Median distance under the null (median of medians) | 0.28° |
| Fraction of the ground band within 0.0085° of a visible road | 1.4% |
| p (at least 4 of 8 sightings that close by chance; exact Poisson-binomial with each burst's own fraction) | **3 × 10⁻⁶** |
| p (Monte Carlo, 4000 draws) | < 2.5 × 10⁻⁴ (no draw was as close) |
| Same test without the contrast vetting | n = 8, median 0.0085°, p = 2 × 10⁻⁶ |

**Speeds.** These come from sightings seen in both frames of a burst. The uncertainty includes the 1 s timestamp resolution and a 0.006° position error, projected onto the road.

| Frames | Δt | Along-road Δ | Speed (2σ range) |
|---|---|---|---|
| 04 → 05 | 6 s | 179 ± 30 m | 30 m/s (17–48 m/s), a car at highway speed |
| 06 → 07 | 2 s | 81 ± 17 m | 41 m/s (16–114 m/s) |
| 06 → 07 | 2 s | 129 ± 104 m | unconstrained: the road points almost at the viewer there |

**Repeated positions.** In v1, lights at nearly the same position 71 s apart (frames 09 and 10) and 5 min apart (04 and 10) looked inconsistent with moving cars. They are not.
- Lights can appear only where the road is in view, and those windows are short, so different vehicles appear at the same few positions.
- On the evening before Thanksgiving, on a road that carries about 1,100–1,600 vehicles a day (TxDOT AADT 2025, stations 189D5 and 189H5A), several vehicles in 5 min is ordinary.

**Refraction.** v1 quoted k ≈ 0.11 from these photos. That estimate is withdrawn. The elevation zero-point *E*₀ is fitted to a skyline computed at k = 0.13, so k is almost degenerate with *E*₀. The small differential effect between road (25–33 km) and skyline (40–70 km) is of the same size as the frame-to-frame residuals left by roll and scale. These photos do not measure k; experiment E2 does.

**Visible/hidden boundary.** Of the US-67 road that projects into each frame, the model calls about half hidden: 48–50% of the 60 m samples. All 8 sightings fall on visible sections: the nearest road sample to each is a visible one. Suppose the model's visible/hidden split had no predictive power, so that a light could appear anywhere on the in-frame road. Then the chance of all 8 landing on visible sections is Π f^n ≈ 0.5⁸ = **0.005**.

This is modest but direct evidence that the modelled hidden stretches are hidden. It is weaker than the position test because it has two limits:
- it assumes vehicles are spread evenly along the road;
- it has only 8 sightings.

## 4. Long exposure (frame 13, 45 s)

The streak search in v1 looked only within ±60 px of the modelled road, which was circular. v2 finds streaks without the model:
- robust 7σ threshold above a local background;
- everything below the fitted skyline;
- elongated components only (width ≥ 60 px, aspect ≥ 5).

Two streaks were found:

| Streak | Columns | Azimuth | Median distance from visible road (model) |
|---|---|---|---|
| 1 | 5582–6000 | 236.90–237.36° | 0.0049° |
| 2 | 2872–2960 | 233.93–234.02° | 0.028° |

Streak 1 is the car traffic at 25–27 km (figure 7b). Streak 2 is short (88 px) and lies 0.03° from the modelled road. Its source is undetermined: it could be a vehicle at the edge of an in-view stretch, or an unrelated light.

## What this does and does not show

**Shows.**
- The lights avoid the stretches the model calls hidden (p ≈ 0.005).
- Real lights photographed from the Viewing Area lie on the modelled visible US-67 to within about 0.01° (8 independent sightings, p ≈ 3 × 10⁻⁶ against random placement in the same band).
- Where the motion can be measured, it matches highway traffic.

**Does not show.**
- **Absolute pointing.** The pointing is fitted to the model's skyline; see E1.
- **The visible/hidden boundary in detail.** Only a weak test (p ≈ 0.005, section 3) is possible. v1's statement that no hidden stretch falls inside these frames was wrong: hidden US-67 lies 0.02° from the sightings.
- **Other sources.** RM 2810, rail and towers are outside the frames.
- **Brightness.** The frames are not photometrically calibrated.
- **Refraction.** As explained above.

## Errors in v1, now corrected

1. **Independence.** v1's probability 0.057⁶ treated six vehicles as independent but used a threshold (0.0206°) chosen as the maximum of the observed distances. That threshold is post hoc. v1 also sampled its random points from all ten frames, including the long-exposure frames 11–13, which were not part of the test. v2 uses a pre-specified statistic and burst-matched null draws.
2. **Distances.** v1 measured distances to 60 m samples, not to the road curve.
3. **Duplicates.** v1 counted a duplicate detection in frame 09 twice.
4. **Circular streak search.** v1's streak search in frame 13 was restricted to ±60 px around the model.
5. **Unsupported refraction estimate.** v1's k ≈ 0.11 is withdrawn.
6. **Focal length.** v1 had the sign of the scale explanation wrong. The effective focal length is about 205 mm.
7. **Hidden stretches.** v1 said no hidden stretch fell inside the frames. In fact about half of the in-frame road is hidden, and hidden road lies 0.02° from the sightings.
8. **Azimuth error.** v1's model had azimuths about 0.12° too high, from a mix of spherical and ellipsoidal geometry. The registration absorbed this error, which is why v1 still matched.
