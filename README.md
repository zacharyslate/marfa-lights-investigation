# Marfa Lights Investigation

[![DOI](https://zenodo.org/badge/1392496709.svg)](https://doi.org/10.5281/zenodo.23046566)

Digital and field investigation of the Marfa Mystery Lights (Presidio County, Texas). The first
stage builds a quantitative model of what an observer at the Marfa Lights Viewing Area can
physically see: the geometry of US‑67 between Shafter and Marfa, terrain occlusion with Earth
curvature and atmospheric refraction, and the artificial light sources in the viewing direction.
The goal is to remove known sources (false positives) before studying anything anomalous.

**The paper.** *Separating the known from the unknown at Marfa, Texas* (version 1.0, 29 September 2026) is the
citable output of this repository: https://zacharyslate.github.io/marfa-lights-investigation/paper.html. How to cite it
is on that page and in `CITATION.cff`. Version 1.0 is archived on Zenodo: doi:10.5281/zenodo.23046856 (all versions: doi:10.5281/zenodo.23046566). Everything else here is working material. It is not field-validated and may change.

Website: **https://zacharyslate.github.io/marfa-lights-investigation/** (GitHub Pages, `docs/` folder)

| Page | What it is |
|---|---|
| `docs/map.html` | Interactive map (USGS imagery) with every layer, a light identifier (bearing → candidate sources, true/magnetic, phone compass, panorama tap), a refraction slider, and a field log that exports CSV |
| `docs/terrain.html` | 3D terrain from the platform to the Chinati Mountains (USGS 3DEP 1 m lidar + 1/3 arc-second DEM at 20 m; relief exaggeration 1–10×; computed creeks, roads, rail, power lines, lit towers, visible US-67, sight lines over the curved Earth, contours; tap for height, distance and bearing). Built by `analysis/terrain3d.py`; three.js r170 (MIT) |
| `docs/photo.html` | Photo checker: load a photo taken from the platform (JPEG, PNG, WebP, HEIC, TIFF, camera RAW via its embedded preview), align it by skyline, tower lights and stars, or by hand, and classify each light against the known-source mask and catalogue. Runs in the browser (exifr, UTIF.js and pako, MIT; libheif, LGPL-3.0). Validated against `analysis/photo_register.py` (bearings within 0.007°) |
| `docs/sightings.html` | Sourced catalogue of documented sightings, studies and published photographs (`analysis/build_catalogue.py` → `docs/data/catalogue.json`), with the re-analysis of 13 published photos (`data/derived/photos_hist/reanalysis.json`; the downloaded images are not redistributed) |
| `docs/history.html`, `science.html`, `place.html`, `visit.html` | Background pages with numbered, linked sources |
| `docs/sightlines.html` | The technical sight-line report |
| `docs/community.html` | Purpose, the dark-sky region, Marfa, good-neighbour guidance, local institutions |
| `docs/sky.html` | Camera sky finder: live camera with skyline, roads, towers, stars and the known-source mask drawn over it; calibrate on a known light and record calibrated bearings (Astronomy Engine, MIT; d3-celestial star data, BSD) |
| `docs/app/` | Installable pocket app (PWA): tonight's darkness, moon and planets (Astronomy Engine), NWS forecast, an hourly refraction forecast (Open-Meteo 2 m and 80 m temperatures → k by Hirt et al. 2010, eq. 2 → km of US-67 in view), a quick light identifier, sighting log, light bingo, red night mode. Works offline via `docs/sw.js` |
| `docs/report.html` | Guided sighting report with an automatic noise check; stays on the device until downloaded or posted |
| `docs/data/site.json` | All map layers, built by `analysis/build_site_data.py` |

## Main results (paper version 1.0)

The numbers below are those of the paper; the working notes in `publication/notes/` record earlier model versions.

- **US-67.** Of the 64.5 km between Shafter and Marfa, about 10 km is in view from the platform at standard
  refraction (k = 0.13), at 229°–238° true, 18–40 km away, always just below the skyline. A strong inversion (k = 1)
  adds only about 1.6 km.
- **Other roads in view.** RM 2810 (Pinto Canyon Road), 13 km at 253°–259°; US-90 and US-67/90 beside the platform at
  280°–288°; and Nopal Road, a county road about 5 km in view at 178°–213°, 7–13 km away (no traffic count; an
  assumed 60 vehicles a day).
- **Brightness.** A northbound car on US-67 is typically magnitude +2.6 on low beam and can outshine Sirius near
  233.7°. It appears in 18 separate windows of median 17 s, drifting about 0.9° per minute. Southbound tail lamps are
  near the naked-eye limit.
- **Known-source mask.** In the band 5 mrad (0.29°) below the skyline, catalogued sources can appear in 33% of the
  120° fan with photographic bearings (±0.3°) and 74% with compass bearings (±3°). Weighted by traffic, 77% of the
  band expects fewer than one ordinary light per 100 hours at photographic precision, and 36% with a compass.

## Repository layout

| Path | Contents |
|---|---|
| `analysis/marfa_ray_fan.py` | 0.5° geodesic ray fan from the viewer to US‑67; intersections; 30 m profile sample points |
| `analysis/marfa_infrastructure.py` | Airfields, railroads, grade crossings, transmission lines, cell sites, power plants — azimuth, distance, and whether each lies in front of US‑67 |
| `analysis/los_browser.js` | Terrain line‑of‑sight engine (USGS 3DEP DEM; curvature + constant‑k refraction; closed‑form critical k) |
| `analysis/marfa_occlusion.py` | Map 1 (standard atmosphere) and Map 2 (refraction range) KMLs, per‑point table, site data |
| `analysis/build_site.py` | Builds `docs/sightlines.html` from `analysis/occlusion_template.html` |
| `analysis/photo_register.py`, `photo_sun_clock.py`, `photo_validate.py`, `photo_figures.py` | Photo validation: register Viewing Area photos to the modelled skyline, check the camera clock with the Sun, test lights against the modelled road (publication note 9). Raw photos are not in git |
| `analysis/build_sw.py` | Regenerates `docs/sw.js` (offline precache list and version hash). Run after any change in `docs/` |
| `analysis/build_site_data.py` | Exports all website map layers to `docs/data/site.json` |
| `analysis/headlight_model.py` | Headlamp photometry model: brightness of a car at every road point, by travel direction |
| `analysis/zone_of_skepticism.py` | Known-source mask polygons (`data/derived/zos.json`, `docs/data/zos.json`) |
| `analysis/weighted_zone.py` | Activity‑weighted mask: expected ordinary lights per hour; per‑night version from measured k, MOR and error |
| `analysis/pub_figures.py` | Publication figures → `publication/figures/` |
| `publication/` | Publication‑ready figures (PDF/SVG/PNG) and method notes (maths, physics, geography, sources) |
| `data/inputs/` | Google Earth trace of US‑67 and reference points; infrastructure layers retrieved from public services |
| `data/derived/` | Line‑of‑sight results exported from `los_browser.js` |
| `outputs/` | KML layers for Google Earth and CSV tables |

## Reproduce

```bash
python -m venv ZACH-venv && source ZACH-venv/bin/activate
pip install -r requirements.txt
python analysis/marfa_ray_fan.py          # -> outputs/Marfa_ray_fan*.{kml,csv}
python analysis/marfa_infrastructure.py   # downloads OurAirports CSVs on first run
python analysis/marfa_occlusion.py        # -> outputs/Marfa_occlusion_*.kml, data/derived/occlusion_page.json
python analysis/build_site.py             # -> docs/sightlines.html
python analysis/headlight_model.py        # -> data/derived/headlights.json
python analysis/build_site_data.py        # -> docs/data/site.json (website map layers)
python analysis/zone_of_skepticism.py     # -> data/derived/zos.json, docs/data/zos.json
python analysis/weighted_zone.py          # -> data/derived/weighted_zone.json, docs/data/zos_rate.json
python analysis/pub_figures.py            # -> publication/figures/*
```

The DEM step (`los_browser.js`) runs in a browser console on the USGS ImageServer page, because
the original analysis environment could not reach USGS directly. Its outputs are committed in
`data/derived/`, so the Python steps reproduce every published figure without it. A pure‑Python
port reading a downloaded 3DEP GeoTIFF is planned.

## Model and known limitations

- Observer eye 1.6 m above the DEM at the Viewing Area; headlight 0.7 m (also 2.5 m).
- Refraction as a constant coefficient k along each path. Near‑ground gradients vary strongly
  with height (Hirt et al. 2010 measured k from about −4 to +16 at 1.8 m), so grazing paths
  need ray‑tracing through a layered temperature profile. This is the main open item.
- ~30 m DEM: road cuts, embankments, vegetation and structures are not resolved; the
  "marginal" class flags where they matter.
- Brightness uses one measured headlamp (NHTSA report 108‑CAN‑17‑004) and an assumed meteorological
  optical range of 100 km; beyond ±12° (high beam) and ±20° (low beam) the beam is extrapolated.
  Humidity affects extinction, not optical bending (Ciddor 1996).
- County and private ranch roads, ranch lights and unregistered structures are not yet catalogued.
- Towers: FCC Antenna Structure Registrations within 90 km (retrieved 2026-09-28), each checked
  against the terrain for whether its top light is in view. Unregistered structures are not included.

## Data sources

- USGS 3D Elevation Program — 3DEPElevation ImageServer (retrieved 2026‑09‑28)
- TxDOT Roadways (on‑system routes), extract 2026‑09‑01 (retrieved 2026‑09‑28)
- TxDOT AADT Annuals (2025 and prior years); FRA grade‑crossing inventory night through‑trains
- Reagan, I. J., et al. (2017). High beam headlamp use rates. *Traffic Injury Prevention*.
- NHTSA FMVSS 108 compliance report 108‑CAN‑17‑004 (headlamp photometry)
- Schaefer, B. E. (1993). Astronomy and the limits of vision. *Vistas in Astronomy* 36, 311–361.
- OurAirports open data — github.com/davidmegginson/ourairports-data
- USDOT BTS NTAD — North American Rail Network, Aviation Facilities (FAA NASR), Railroad Grade Crossings (FRA inventory)
- Electric Power Transmission Lines (HIFLD‑derived); FCC Antenna Structure Registration; Cellular Towers (FCC ULS); EIA‑860 Power Plants
- Hirt, C., Guillaume, S., Wisbar, A., Bürki, B., Sternberg, H. (2010). *J. Geophys. Res.* 115, D21102. doi:10.1029/2010JD014067
- Ciddor, P. E. (1996). Refractive index of air: new equations for the visible and near infrared. *Applied Optics* 35(9), 1566–1573.

## Licence

Paper, figures and data: CC BY 4.0 (`LICENSE-CC-BY-4.0.txt`). Code: MIT (`LICENSE`). Photographs by Zach Warren:
all rights reserved. Third-party images, libraries and data keep their own licences. Details in `LICENSING.md`.

## Author

Zach Warren — UAM Madrid / ICV‑CSIC.
