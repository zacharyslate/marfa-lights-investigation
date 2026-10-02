# 14. Photo checker, published-photo re-analysis, refraction forecast, sightings catalogue (2 Oct 2026)

## Photo checker (docs/photo.html, docs/assets/photo.js)
- Pinhole camera at the platform (30.2751108 N, 103.8827973 W, eye 1.6 m); pointing = bearing, tilt, roll; focal length in pixels.
- Lens from EXIF: 35 mm equivalent by the diagonal (CIPA), else FocalLength x FocalPlaneXResolution. Refined within +-6 % in skyline fits (EXIF 35 mm equivalents are rounded; e.g. the a6300 + 210 mm reports 315 mm, the fit gives ~327 mm, the research pipeline 52 362 px = 328 mm).
- Skyline route: per column, the topmost brightness/colour STEP (wires and thin lines rejected by a step test); grid search over bearing (and lens, 2-90 deg in 15 % steps when unknown) and roll, tilt from the median offset; best cell per bearing bin seeds Nelder-Mead; ambiguity = next-best basin more than half a field away.
- Lights route: RANSAC over pairs of detected points x pairs of anchors (lit towers in view, stars <= mag 2.5 and planets when the time is known, Astronomy Engine with normal refraction).
- Light detection: residual over a 16-px box background, significance against a 24-px local texture; ranked by significance x sqrt(area) so hot pixels lose to real (often bloomed) headlights.
- Verdicts: star/planet match; foreground (below the highest terrain within 10 km, i.e. nearer than 10 km); above the skyline; inside the known-source mask (tier A if sigma <= 0.15 deg, else tier B up to 3 deg) with up to four candidate sources; outside the mask = "not explained by the catalogue"; sigma > 3 deg, off-platform GPS, or outside 150-300 deg = can't tell.
- Formats: JPEG/PNG/WebP natively, TIFF via UTIF.js + pako, HEIC via libheif (wasm, loaded on demand), RAW via the largest embedded JPEG preview.

## Validation against the research pipeline (analysis/photo_register.py)
| frame | bearing JS | bearing PY | tilt JS | tilt PY | lens diff |
|---|---|---|---|---|---|
| p04 | 233.652 | 233.647 | -0.247 | -0.249 | 0.8 % |
| p05 | 233.759 | 233.752 | -0.207 | -0.212 | 0.5 % |
| p06 | 234.811 | 234.809 | -0.089 | -0.095 | 0.1 % |
| p08 | 234.817 | 234.813 | -0.054 | -0.056 | 0.2 % |
| p10 | 234.636 | 234.631 | -0.059 | -0.060 | 0.2 % |
| p13 | 234.073 | 234.070 | -0.261 | -0.287 | 0.2 % |
Lights: p04 233.778/-0.218 (PY 233.771/-0.221); p08 234.347/-0.253 (PY 234.343/-0.254). Same result for PNG/WebP/TIFF/HEIC copies of p08, and for an EXIF-free PNG (lens recovered from the skyline to 0.1 %).

## Re-analysis of published photographs (data/derived/photos_hist/reanalysis.json)
- 39 published photos inventoried (data/inputs/published_photos_research.json); 13 downloaded with the author's permission to download (2 Oct 2026); images kept out of git.
- Henderson 2014-07-26 a/b (CC BY 2.0): skyline fits 1.3 / 2.6 px (+-0.02-0.03 deg); light at 233.81/-0.22 and 233.66/-0.18 deg: inside the tier-A mask on the visible US-67 stretch (~31-33 km), moving 0.15 deg along the road in 97 s. Figures: docs/img/val_henderson_{a,b}-*.webp.
- Pettengill 2015-08-15 (CC BY-NC-ND; measurements only): stars (6 + Saturn, 3.1 px) give ~19 mm-equivalent lens; skyline-only fit disagrees by ~11 deg at the horizon (wide-angle distortion), so +-1 deg assumed: horizon lights at ~185 deg true, tier-B mask, Texas Pacifico rail (4 km) / Nopal Road (11 km) sector, ~30 deg left of US-67.
- Can't tell (7): Hanson 2009 (no skyline features), Barclay 2006 (only a 1024-px processed copy), Zilar 2007 (no fit; probably not from the platform), DBC 2005, Parrott 2009, KM&G-Morris 2014 (truncated original), Yensel 2021 (3000 mm close-up). Klebs 2016: SE, outside the modelled sector. Jay Lee 2009: control (US-90 trail). Suter 2015: beside US-67, excluded.
- Lesson: automatic global skyline fits can land in a wrong basin on hazy frames (Henderson a first gave 256.6 deg at 4.5 px; fixed by seeding per bearing bin). The checker flags near-ties; visual confirmation of the skyline remains essential.

## Refraction forecast (docs/app, Tonight)
- k = 503 p / T^2 (0.0343 + dT/dz) (Hirt et al. 2010, JGR 115, D21102, eq. 2), dT/dz = (T80 - T2)/78 m from the Open-Meteo forecast (CC BY 4.0), p = surface pressure.
- km of US-67 in view at k from the model's per-point k_crit (site.json hwy): 10.0 km at k = 0.13, 11.4 at 0.5-0.75, 11.6 at 1.0, 12.4 at 2.0. Refraction mainly lifts and distorts distant lights; it adds little road.
- Caveat: forecast models under-resolve shallow nocturnal surface inversions.

## Sightings catalogue (docs/sightings.html)
- 51 documented sightings/campaigns (data/inputs/sightings_research.json), each with sources, 'opened' flags and a model-testability rating (5 yes, 15 partly, 31 no). Spot-checked: Texas Monthly 2006 (Hall's tower-light description, San Angelo Times 1945); Stephan et al. 2011 JASTP 73(13):1953-1958.
