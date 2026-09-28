# 7. Data sources and provenance

> **Superseded numbers (2026-09-28).** This working note describes the v1 model. The line-of-sight model has since been rebuilt (exact WGS84 geometry, 1 m lidar terrain with point-cloud obstructions, Monte Carlo classes, height-dependent ray tracing); see [note 11](11_model_v2_methods.md) for the current methods and numbers, and [note 12](12_experimental_design.md) for the planned experiments. Where this note and note 11 disagree, note 11 is correct.

| Layer | Source | Retrieved | Used for |
|---|---|---|---|
| Elevation | USGS 3D Elevation Program, `3DEPElevation` ImageServer (1″ and 3″ grids) | 2026-09-28 | line of sight, skyline, profiles, road grade |
| US-67 trace, viewer, reference points | Author's Google Earth KML (`data/inputs/Investigation_Marfa.kml`) | — | fan geometry, US-67 analysis |
| State roads | TxDOT Roadways FeatureServer (ArcGIS Online, TxDOT organisation), `EXT_DATE` 2026-09-01 | 2026-09-28 | RM 2810, US-90, FM 170, SH 118, RM 169, FM 1112, SH 17 |
| Railroads | USDOT BTS NTAD North American Rail Network Lines | 2026-09-28 | rail layer, rail line of sight |
| Grade crossings | FRA crossing inventory (via NTAD) | 2026-09-28 | crossing layer |
| Airfields | OurAirports open data, cross-checked against FAA NASR (via NTAD Aviation Facilities, effective 2026-09-03) | 2026-09-28 | airfield layer, aerostat site |
| Towers | FCC Antenna Structure Registration (ASR) | 2026-09-28 | lit towers and their lighting specification |
| Transmission lines, cell sites, power plants | HIFLD-derived layers; FCC ULS; EIA-860 | 2026-09-28 | context layers |
| Headlamp photometry | NHTSA compliance report 108-CAN-17-004 (2016 Ford Focus S) | 2026-09-28 | beam model |
| Magnitude scale | Schaefer (1993), *Vistas in Astronomy* 36, 311 | — | lux to magnitude |
| Magnetic declination | NOAA WMM2025 | — | bearings |

## Reproducibility

The numbers in these notes and figures come from the code in `analysis/` and the committed files in `data/derived/`. The DEM queries were run in a browser (`analysis/los_browser.js` and the equivalent functions for the roads and skyline) because the analysis environment could not reach USGS directly. Their outputs are committed, so the Python steps reproduce the figures exactly.

## Known gaps in the catalogue

- County and private ranch roads.
- Ranch yard lights.
- Unregistered structures.
- Train schedules and traffic counts for the nights of observation.
- Aircraft tracks: these can be logged in the field from ADS-B receivers.

Each gap is a false-positive source that the Zone of Skepticism does not yet cover.
