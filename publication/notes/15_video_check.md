# 15. Checking a "Marfa lights" video against the model (7 Oct 2026)

Input: an 18.4 s phone video (1920×1080, 30 fps, 553 frames) supplied by the author. It has no date, time, location or camera metadata (re-encoded). Source and licence still to be recorded before any publication.

## Method (analysis/video/video_track.py, video_render.py)
- Camera at the platform (assumed), pinhole model as in the photo checker.
- Per frame: skyline detected (topmost sky-to-land step), then bearing, tilt, roll and focal length fitted to the modelled skyline (k = 0.13); columns near lights excluded; bad local fits re-seeded by a bearing × lens grid.
- Result: every frame fits; median residual 1.6 px (≈ 0.011°), 95th percentile 1.9 px; focal length ≈ 8,200 px throughout (≈ 13° wide, heavy digital zoom); roll −0.4° to −1.4° (hand-held).
- Lights: compact spots brighter than a 41 px local background, kept only if below the modelled skyline. Exactly four lights were found; nothing else passed.

## Results
| Light | Colour | Bearing (true) | Motion | Nearest model source | Implied distance / speed |
|---|---|---|---|---|---|
| A | white | 230.59° → 230.75° | +0.54°/min | visible US-67, median 0.03° | 36.5 km, ~114 km/h toward Marfa |
| B | white | 233.76° → 233.83° | +0.23°/min | visible US-67, 0.04° | 31.8 km, ~118 km/h toward Marfa |
| C | white | 236.61° → 236.89° | +0.94°/min | visible US-67, 0.06° | 27.0 km, ~106 km/h toward Marfa |
| D | red | 229.33°, stationary | flashes every 2.0 s (≈ 30/min, ~40% on) | 0.25° from US-67; 1.0° left of the registered lit tower | see below |

- Speeds assume the light is on the road (chainage change implied by the bearing change); they are a consistency check, not an independent measurement.
- **Light C appears and drops out where the model says the road is hidden.** It first shows at 236.65° (model: hidden until 236.63°, marginal 236.63°, visible from 236.66°). It vanishes from 12.8 s to 14.6 s while its fitted bearing crosses 236.80°–236.835°; the model has a 60 m hidden sample at 236.81° (band ≈ 236.795°–236.825°). At ~106 km/h that gap lasts 2–4 s, as observed.
- **Light D** is a red beacon flashing at ~30 per minute, typical of a tower obstruction beacon. Its elevation (−0.25°) matches the top of FCC ASR 1053636 (Big Bend Telephone Co., 89.3 m, 1976, FCC lighting paragraphs 1, 3, 11, 21) at −0.28°. But it lies 1.0° left of that tower's registered position (230.33°, 20.41 km). At the registered distance the light would be at 30.15502 N, 104.04348 W, 357 m from the registered coordinates (bearing 141°). No light is seen at the registered position itself. Either the registered coordinates are off by ~360 m or this is another lit structure. **To check:** satellite imagery at the implied position, and a bearing on the beacon from the platform.

## Verdict
All four lights in this clip are explained by catalogued sources: three cars on US-67 and one tower beacon (position to confirm). Nothing in it needs anything unusual.

## Caveats
- Observer position assumed to be the platform; the skyline fit is consistent with that, but a few hundred metres would not be detectable from the skyline alone.
- No lens distortion model (phone, digital zoom; effect small near the frame centre).
- Detection threshold is fixed; fainter lights could be missed.
- Date and time unknown, so traffic, sky and refraction for that night cannot be checked.

## Outputs (not committed; third-party video)
- marfa_video_model_overlay.mp4: the original frames with the model drawn per frame.
- marfa_video_side_by_side.mp4: stabilised view with the model, bearing-versus-time tracks with hidden-stretch bands, map of US-67 with implied car positions and sight lines, per-light cards.
