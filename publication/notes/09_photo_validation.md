# 09 · Photo validation of the sight-line model

The line-of-sight model (notes 01–03) predicts where headlights on US-67 can appear from the Viewing Area. This note tests that prediction against photographs taken from the Viewing Area.

## Data

- **Photographer:** Zach Warren. Photos taken 21 November 2018.
- **Camera and lens:** Sony ILCE-6300 (APS-C, 23.5 mm sensor width, 6000 px) with an E 55–210 mm lens at 210 mm.
  - Nominal focal length in pixels: *f* = 210 / (23.5/6000) = 53,617 px, or 936 px per degree.
- **Viewing Area sequence:** ten frames, camera time 19:12:03–19:26:12.
  - Exposures run from 1/25 s to 45 s.
  - Frames were exported from Lightroom at 6000 × 3376 px.
- **Clock check:** one sunset frame from the same camera, at camera time 18:49:40.
- **Where things are kept:**
  - Raw files are kept outside git (`data/photos_raw/`).
  - Results are in `data/derived/photos/`.
  - Scripts: `analysis/photo_register.py`, `photo_sun_clock.py`, `photo_validate.py` and `photo_figures.py`.

## 1. Registration

The sky–land boundary was traced in each frame. It is the row where red minus blue drops below 45 % of its value in the sky, with the image smoothed over 9 × 9 px.

A rectilinear camera model has four parameters: pointing azimuth *A*₀, pointing elevation *E*₀, roll, and a scale factor on *f*. These were fitted by robust least squares so that the traced boundary matches the modelled skyline. The modelled skyline comes from `docs/data/site.json`, is sampled every 0.1° in azimuth, and uses k = 0.13.

**Results:**

| Frame | Exposure | *A*₀ (° true) | Skyline RMS (°) | Best alternative RMS (°) | Ratio |
|---|---|---|---|---|---|
| 04 | 1/25 s | 233.52 | 0.011 | 0.028 | 2.6 |
| 05 | 1/25 s | 233.63 | 0.011 | 0.030 | 2.7 |
| 06 | 1/25 s | 234.69 | 0.008 | 0.056 | 6.7 |
| 07 | 1/25 s | 234.67 | 0.008 | 0.055 | 6.6 |
| 08 | 1/15 s | 234.69 | 0.006 | 0.051 | 9.0 |
| 09 | 1.3 s | 234.58 | 0.006 | 0.049 | 8.4 |
| 10 | 1.6 s | 234.51 | 0.006 | 0.045 | 7.6 |
| 11 | 30 s | 234.52 | 0.006 | 0.045 | 7.7 |
| 12 | 40 s | 233.94 | 0.016 | 0.022 | 1.4 |
| 13 | 45 s | 233.95 | 0.017 | 0.023 | 1.4 |

- The fitted scale is 0.971 ± 0.001 in every frame. Lightroom's lens-profile correction slightly enlarges the image, which probably explains this. It is consistent across frames and independent of the other parameters.
- Roll is between −0.65° and +0.28°.
- The skyline alone discriminates weakly in frames 12–13: the best alternative pointing fits only 1.4 times worse. Their pointing is confirmed independently because the headlight streaks fall on the modelled road (section 4). A wrong pointing would put them several degrees away.

## 2. Camera clock

The sunset frame registers to the skyline with an RMS of 0.003°. It points at 244.6° true.

- **Measured sun:** the centroid of the saturated solar disc is at 246.25° azimuth and 0.70° elevation.
- **Matching the sun's position:** computed with Astronomy Engine (Python), including standard refraction, as seen from the Viewing Area.
- **Result:** the best match puts the camera clock 59 min ahead of Central Standard Time (UTC−6). The remaining mismatch is 0.14°.
- **Likely cause:** the camera was still set to daylight time after the 4 November 2018 changeover.
- **What the mismatch probably comes from:**
  - bloom biasing the saturated centroid;
  - refraction at 1.5 km altitude being about 15 % below the standard value.

  Neither changes the conclusion.
- **Corrected times:** the car frames were taken 18:12–18:26 CST, about 20–35 minutes after sunset, during civil twilight.

## 3. Lights in the short exposures

**Detection:**
- A high-pass image is made by subtracting a 21 × 21 px median.
- A detection must exceed 7 robust standard deviations.
- Its area must be 4–600 px.
- It must lie between the 10 km ridge line and 0.027° below the skyline. Anything more than 10 km away must appear above the 10 km ridge line.

**Vetting:** a detection is kept only if its peak is at least 1.20 times the median of the surrounding 120 × 80 px. This rejects bright sky or ground beside sensor dust and a hair on the sensor. It agreed with a visual check of all 50 detections, keeping 45.

**Result:**
- 12 point-like lights were found in frames with exposures of 1.6 s or less (frames 04–10).
- Their angular distance from the nearest US-67 point that the model classes as visible or marginal:

| Quantity | Value |
|---|---|
| Median distance | 0.0112° (about 10 px; about 6 m at 30 km) |
| Maximum distance | 0.0206° |
| Road distance of the matched points | 25–33 km |
| Chance that a random point in the same band lands within 0.0206° | 0.057 |

- The random points were drawn uniformly between the 10 km ridge line and the skyline, over all ten frames.
- The 12 lights are not independent. The same car appears in consecutive frames: 04/05, 06/07 and 09. About six independent vehicles are involved, so the chance that all of them fall this close to the road by accident is roughly 0.057⁶ ≈ 3 × 10⁻⁸.

**Height of the lights (refraction):**
- Compared at the same azimuth, the lights sit 0.003° above the modelled road on average (range −0.003° to +0.009°).
- The registration pins the skyline, which is 42–69 km away, at k = 0.13. The road is 25–33 km away. A different k would therefore shift the road relative to the skyline by (*d*_road − *d*_sky) Δk / 2R.
- The least-squares estimate is k ≈ 0.11. Its formal error of ±0.01 leaves out:
  - DEM vertical error (about 1–2 m, or 0.002–0.004° at 30 km);
  - uncertainty in the height of the lamps;
  - residual registration error.

  A realistic uncertainty is ±0.05. The evening had ordinary refraction, not an inversion.

## 4. Long exposure (frame 13, 45 s)

- Moving cars leave streaks. The brightest row was traced in 68 image columns within ±60 px of the modelled road, covering 230.6°–237.2° azimuth.
- Median absolute offset from the model: 0.005°.
- Mean offset: −0.007°.
- RMS offset: 0.021°. This is inflated by columns where the trace picked up background rather than the streak.

## What this does and does not show

**What it shows:**
- The combination of terrain model, road trace, refraction and camera model places real headlights where the model predicts, to about 0.01°. This supports the positions the identifier, the Zone of Skepticism and the app use for the US-67 stretch at 230°–238°.

**What it does not show:**
- **The visible/hidden boundary.** No stretch the model calls hidden falls inside these frames. The nearest hidden US-67 points are more than 0.7° from any detected light, so there was nothing to test it against.
- **The other sources.** RM 2810 at 253°–259°, the railroads and the towers are all outside these frames.
- **Brightness.** The photos are not photometrically calibrated, so the headlight brightness model (note 4) is not tested.

**Next steps:**
- Photograph RM 2810 and the hidden stretch at about 240°.
- Include a star field in the same frame, or a calibrated exposure series, to test brightness.
- Take a simultaneous sequence from a second location, which would allow triangulation.
