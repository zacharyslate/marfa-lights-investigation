# Publication materials

Figures and method notes for the Marfa Lights manuscript. Everything here is generated from the code in `../analysis/` and the data in `../data/`. Please do not edit figures by hand: change the script and re-run it.

**Paper:** [`manuscript/marfa_ajp.tex`](manuscript/marfa_ajp.tex), self-published on the website (`docs/paper.html`). See [`manuscript/README.md`](manuscript/README.md) for the build and how to release a new version.

**Status: preliminary.**
- **Model.** The line-of-sight model is version 2 (`analysis/marfa/`; methods, verification and robustness in [note 11](notes/11_model_v2_methods.md)). It uses exact WGS84 geometry, USGS 1 m lidar terrain with point-cloud obstructions, and GEOID12B. Visibility classes come from a Monte Carlo, and a height-dependent ray trace is included. It is covered by 22 unit tests.
- **Photos.** The geometry has been checked against one evening of photographs (Figure 7, [note 9](notes/09_photo_validation.md)).
- **Not yet field-tested.** RM 2810, the brightness model and night-time refraction. The planned experiments are in [note 12](notes/12_experimental_design.md).
- **Older notes.** Notes 01–08 are v1 working notes; their numbers are superseded by note 11.

## Figures (`figures/`)

Each figure is provided as vector PDF (fonts embedded), SVG and 300 dpi PNG. The widths are 180 mm (double column). Colours come from the Okabe–Ito colour-blind-safe palette (Okabe & Ito 2008).

**Figure 1 · `fig01_study_area`: The 120° viewing fan.**
- Rays at 0.5° from the Marfa Lights Viewing Area (star), 157.3°–277.3° true, over a USGS 3DEP hillshade with 200 m contours.
- Rays that cross US-67 stop at the first crossing. The rest run 80 km.
- Roads are coloured by whether a 0.66 m headlamp is in view from the platform at k = 0.13 (v2 Monte Carlo classes):
  - US-67: vermilion = visible, orange = marginal.
  - Other TxDOT state roads: purple = visible.
  - Grey: hidden.
- Blue lines are railroads. Diamonds are FCC-registered towers with aviation lighting: filled if the top light is in view, hollow if hidden.
- Axes are km east and north of the viewer, in an azimuthal-equidistant projection.

**Figure 2 · `fig02_panorama_zos`: The view from the platform and the known-source mask.**
- (a) Bearings 155°–300° true; (b) the US-67 / RM 2810 sector at 224°–262°.
- Grey layers are terrain silhouettes: the far skyline, then the maximum elevation angle within 45, 25 and 10 km. The black line is the skyline at k = 0.13.
- Points are the apparent positions, at k = 0.13, of headlamps on roads in view and of locomotive headlamps on track in view. Diamonds are lit towers.
- Green fill is the known-source mask for photographic pointing: the locus of every catalogued source for 0 ≤ k ≤ 1, widened by ±0.3° in bearing and ±0.1° in elevation. The dashed green outline is the mask for compass pointing (±3°, ±0.25°).
- The vertical scale is exaggerated; the factor is printed on each panel. The top axis gives magnetic bearing, using a declination of 6.2° E.
- Definition: note 5.

**Figure 3 · `fig03_headlights`: How bright a car would look.**
- (a, b) Iso-candela maps of one production U.S. headlamp: 2016 Ford Focus S, NHTSA report 108-CAN-17-004. Crosses mark the measured test points. Shaded margins are extrapolated.
- Coloured dots mark where the Viewing Area falls in the beam of cars on US-67 and RM 2810 heading toward Marfa.
- (c) Predicted apparent magnitude of a car facing the platform, for low and high beams. The model uses two unresolved lamps and MOR = 100 km. Bars show ±0.5° of aim and pitch and the range of fall-off beyond the measured angles.
- Definition: note 4.

**Figure 4 · `fig04_sightlines`: Terrain cross-sections along four bearings.**
- Ground elevation is reduced by E + d²(1−k)/2R, with k = 0.13, so every sight line from the eye is a straight line through the origin.
- Coloured ground is in direct view. The dotted line is the steepest (skyline) ray. Triangles mark road or track crossings.
- The bearings are:
  - 233.6°: US-67 in view on the straight that points at the platform.
  - 240°: US-67 hidden behind the Mitchell Flat rise.
  - 255.6°: RM 2810 in view in the Chinati foothills.
  - 190°: Texas Pacifico track in view 4–5 km away.

**Figure 5 · `fig05_refraction`: Sensitivity to refraction.**
- (a) Length of US-67 and of RM 2810 whose critical refraction coefficient is ≤ k, plotted against k. This includes the grazing (marginal) part: In model v2, US-67 (Shafter–Marfa) has 9.5 km robustly visible plus 0.5 km marginal at k = 0.13. The top axis converts k to the temperature gradient, using Hirt et al. (2010) at 850 hPa and 283 K.
- (b) Rise in apparent elevation for a change Δk in refraction, plotted against distance.

**Figure 6 · `fig06_weighted_zone`: The activity-weighted known-source mask.**
- Colour shows the expected number of catalogued ordinary lights per hour passing through each part of the view on a standard night: k = 0.13, MOR 100 km, observer error ±0.3° × ±0.1°.
- Road rates use TxDOT AADT, only for the direction facing the platform, weighted by the headlight detectability of note 4. Rail rates use FRA night through-train counts.
- The shading uses one ordinal blue ramp. Unshaded ground receives fewer than 0.01 lights per hour. Hatching marks permanent lights (towers, towns, skyglow, the aerostat).
- Definition and sensitivity: note 8.

**Figure 7 · `fig07_photo_validation`: Photo check of the sight-line model.**
- Photos by Zach Warren from the Viewing Area, 21 November 2018, Sony ILCE-6300 at 210 mm.
- (a) Frame 06 (1/25 s, 18:13 CST) registered to the modelled skyline (white, RMS 0.008°), with the 10 km and 25 km ridge lines and the modelled visible stretch of US-67 (yellow). The circled lights are cars 26–33 km away.
- (b) Frame 13 (45 s): headlight streaks against the modelled road. Median offset 0.005°.
- (c) Cumulative distribution of the angular distance from the modelled US-67 for the 12 lights detected in short exposures, compared with random points in the same band.
- Method and caveats: note 9.

## Notes (`notes/`)

| File | Contents |
|---|---|
| `01_geometry_and_rays.md` | observer, the fan, geodesics, angular size at range |
| `02_curvature_and_refraction.md` | curvature drop, refraction coefficient, Hirt formula, why humidity doesn't bend light, limits of a constant k |
| `03_line_of_sight.md` | DEM, visibility test, closed-form critical k, visibility classes, cross-sections, skyline |
| `04_headlight_brightness.md` | photometry v2: car-frame angles, market-weighted beams and FMVSS brackets, magnitude and detection threshold, one car over time, occupancy, limitations |
| `05_zone_of_skepticism.md` | definition, construction, coverage, what it leaves out |
| `06_geography_geology_climate.md` | setting, with sources |
| `07_data_sources.md` | provenance table and catalogue gaps |
| `08_weighted_zone.md` | activity-weighted zone: model, parameters, results, motion signature, per-night use |
| `09_photo_validation.md` | registration of Viewing Area photos to the model, camera clock from the Sun, lights and streaks against the modelled road, what is and isn't tested |

## Regenerate everything

Run from the repository root, using the project virtual environment (`ZACH-venv`):

```bash
python analysis/marfa_ray_fan.py
python analysis/marfa_infrastructure.py
python analysis/marfa_occlusion.py
(cd analysis && python -m marfa.run_photometry && python -m marfa.run_traffic)   # -> data/derived/los2/photometry.*, traffic_us67.json (needs roads_lidar.npz from marfa.run_los)
python analysis/headlight_model.py      # -> data/derived/headlights.json
python analysis/build_site_data.py      # -> docs/data/site.json
python analysis/zone_of_skepticism.py   # -> data/derived/zos.json, docs/data/zos.json
python analysis/weighted_zone.py        # -> data/derived/weighted_zone.json, docs/data/zos_rate.json
python analysis/pub_figures.py          # -> publication/figures/*
python analysis/figs_to_web.py && python analysis/build_sw.py   # -> docs/img/*.webp, docs/sw.js
```

## Reference

- Okabe, M., Ito, K. (2008). *Color Universal Design (CUD): How to make figures and presentations that are friendly to colorblind people.* J*Fly. https://jfly.uni-koeln.de/color/
