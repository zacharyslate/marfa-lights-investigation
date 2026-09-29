# Marfa Lights Investigation

Digital and field investigation of the Marfa Mystery Lights (Presidio County, Texas). The first
stage builds a quantitative model of what an observer at the Marfa Lights Viewing Area can
physically see: the geometry of US‑67 between Shafter and Marfa, terrain occlusion with Earth
curvature and atmospheric refraction, and the artificial light sources in the viewing direction.
The goal is to remove known sources (false positives) before studying anything anomalous.

**The paper.** *Separating the known from the unknown at Marfa, Texas* (version 1.0, 29 September 2026) is the
citable output of this repository: https://zacharyslate.github.io/marfa-lights-investigation/paper.html. How to cite it
is on that page and in `CITATION.cff`. Everything else here is working material. It is not field-validated and may change.

Website: **https://zacharyslate.github.io/marfa-lights-investigation/** (GitHub Pages, `docs/` folder)

| Page | What it is |
|---|---|
| `docs/map.html` | Interactive map (USGS imagery) with every layer, a light identifier (bearing → candidate sources, true/magnetic, phone compass, panorama tap), a refraction slider, and a field log that exports CSV |
| `docs/history.html`, `science.html`, `place.html`, `visit.html` | Background pages with numbered, linked sources |
| `docs/sightlines.html` | The technical sight-line report |
| `docs/community.html` | Purpose, the dark-sky region, Marfa, good-neighbour guidance, local institutions |
| `docs/sky.html` | Camera sky finder: live camera with skyline, roads, towers, stars and the known-source mask drawn over it; calibrate on a known light and record calibrated bearings (Astronomy Engine, MIT; d3-celestial star data, BSD) |
| `docs/app/` | Installable pocket app (PWA): tonight's darkness, moon and planets (Astronomy Engine), NWS forecast, a quick light identifier, sighting log, light bingo, red night mode. Works offline via `docs/sw.js` |
| `docs/report.html` | Guided sighting report with an automatic noise check; stays on the device until downloaded or posted |
| `docs/data/site.json` | All map layers, built by `analysis/build_site_data.py` |

## Current results (2026‑09‑28)

At standard refraction (k = 0.13), a 0.7 m headlight on US‑67 is visible from the Viewing Area
along only ~9.3 km of the 64.6 km modelled, in a band at 228.8°–238.2° true, 24–40 km away.
A further ~7.4 km is marginal (sub‑DEM detail decides it), and ~47.9 km is hidden by terrain.
Even strong night‑time inversions (k = 1) extend the visible road to only ~12.8 km. See the site
for the maps, a panorama from the platform, and cross‑sections.

Update (2026‑09‑28, 120° fan):
- **RM 2810 (Pinto Canyon Road) is also in view**: ~27 km at 252.9°–259.1° true, 32–53 km away,
  just below the skyline. The earlier statement that nothing between 238° and 277° could be a car
  was wrong; it holds only for US‑67.
- **Headlight direction matters.** Northbound cars on the US‑67 straight at ~233.5° point within
  3–5° of the platform. With high beams they are predicted near magnitude −2, brighter than Sirius
  (one measured production headlamp; see `publication/notes/04_headlight_brightness.md`).
- **Known-source mask** (formerly "Zone of Skepticism"). The mask is the region of the view where a catalogued light can appear.
  In the 0.29° band just below the skyline it covers ~33% of the fan with instrumented bearings
  (±0.3°) and ~74% with hand‑compass bearings (±3°).
- **Activity‑weighted zone.** Weighting each source by how often it produces a light (TxDOT traffic
  counts, FRA night‑train counts, headlight detectability) leaves ~80% of that band with fewer than
  one catalogued ordinary light per 100 hours at instrumented precision. With a hand compass the
  share falls to ~36%. See `publication/notes/08_weighted_zone.md`.

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
