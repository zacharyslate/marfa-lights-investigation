# 8. The activity-weighted Zone of Skepticism

> **Superseded numbers (2026-09-28).** This working note describes the v1 model. The line-of-sight model has since been rebuilt (exact WGS84 geometry, 1 m lidar terrain with point-cloud obstructions, Monte Carlo classes, height-dependent ray tracing); see [note 11](11_model_v2_methods.md) for the current methods and numbers, and [note 12](12_experimental_design.md) for the planned experiments. Where this note and note 11 disagree, note 11 is correct.

> **Photometry v2 update (2026-09-29).** The rates now use the v2 brightness model (note 4): UMTRI market-weighted beams, lidar grades, MOR 145 km (NPS Big Bend average visual range) and m_lim = 5.86 (Crumey 2014, μ = 21, F = 2). Weighted quiet fraction of the band 0–5 mrad below the skyline: **0.805** standard night (k = 0.13), 0.779 strong inversion (k = 1), 0.797 if southbound tail lamps at the FMVSS maximum are counted (new 'tail_max' scenario, an upper bound). Tail lamps are no longer described as "well below the limit": at the regulatory maximum they are near it (note 4).

## Why weight the zone

The binary zone (note 5) marks where a catalogued light *can* appear. It treats a highway with about 1,500 vehicles a day the same as a railroad that the FRA inventory lists with zero or one night train. In the binary version, the Texas Pacifico track alone accounted for more than half of the tier-A coverage in the band just below the skyline.

The weighted zone replaces "can appear" with "how often does appear". The result is the expected number of ordinary lights per hour passing through each patch of the view on a given night.

## Model

For a patch at bearing *a* and elevation α, the rate is

    λ(a, α) = Σ_lines  max_{samples of the line in the patch}  q · P_detect · V

The terms are:

- **Roads.** The flow per direction is q = AADT × *s* / 2 vehicles per hour, where *s* is the fraction of daily traffic in one night hour (both directions).
  - AADT comes from the nearest TxDOT count station on the same route. The value used is the highest of 2025 and the two previous years, because single years can be low outliers. RM 2810's outer station reports 1 vehicle/day for 2025 but 24 for the year before.
  - Only the direction whose headlamps face the platform (|h| < 90°) counts. Tail lamps are omitted: at 20–50 km they are well below the naked-eye limit.
  - **P_detect** = p_high·[m_high ≤ m_lim] + (1 − p_high)·[m_low ≤ m_lim]. The magnitudes come from note 4, corrected to the night's MOR.
  - **V** = 1 where the road is in view at the night's *k*, 0.5 for the marginal class, and 0 otherwise.
- **Railroads.** The rate is q = night through-trains / 12 h.
  - FRA Form F 6180.71 defines night as 6 PM to 6 AM. The value used is the highest reported at any crossing of that railroad within 90 km: Union Pacific 6 (0.5 per hour); Texas Pacifico 1 (0.083 per hour).
  - Of the Texas Pacifico crossings, 46 report 0 night trains and 6 report 1.
  - Track in view counts as detectable, because of the locomotive headlight and ditch lights.
- **Lines.** A car passes a given patch once, so rates are the **maximum** along one road or track and are **summed** across lines.
- **Observer error.** Each sample is spread over the observer's error box before combining.
- **Permanent lights.** Lit towers, towns, skyglow and the aerostat are not rates. They are kept as a separate "permanent light" mask (hatched in Figure 6).

## Parameters

| Parameter | Value | Status |
|---|---|---|
| *s*, share of AADT per night hour | 0.02 | **assumption.** No verified night-hour share was found for these roads. The FHWA pocket guide (FHWA-PL-18-027) gives hourly factors only for trucks. |
| p_high, share of drivers on high beam | 0.25 | Reagan et al. (2017) measured 18% across their sites and cite about 25% for isolated vehicles on unlit roads in earlier work |
| m_lim, detection limit | 6.0 | typical naked-eye limit at a dark site (Schaefer 1993) |
| MOR | 100 km | assumption for a clear desert night (note 4) |
| Error box | ±0.3° bearing, ±0.1° elevation | tier A, instrumented |
| Car speed for motion | 100 km/h | nominal |

## Results

The results cover the band from the skyline down 5 mrad (0.29°), inside the 157°–277° fan.

| Scenario | Permanent light | ≥ 1 per hour | 0.1–1 | 0.01–0.1 | Quiet: < 0.01 per hour, no permanent light |
|---|---|---|---|---|---|
| Standard night (k = 0.13) | 2.8% | 2.8% | 3.3% | 11.4% | **80%** |
| Strong inversion (k = 1) | 2.9% | 2.8% | 3.3% | 12.9% | 78% |
| Hand compass (±3°, ±0.25°) | 22.5% | 10.1% | 9.6% | 38.8% | **36%** |
| Share *s* = 1% or 4% | | 2.7–4.5% | | | 80% |
| MOR 50 km | | 2.7% | | | 81% |
| m_lim = 4 (casual observer) | | 2.4% | | | 82% |
| Texas Pacifico assumed idle (0 trains) | | 2.8% | | 0% | 91% |

Peak rates along each line (standard night):

| Line | Peak rate | Notes |
|---|---|---|
| US-67 northbound | ≈ 15 per hour | 228.7°–251.8° |
| US-67/90 beside the platform | ≈ 28 per hour | |
| US-90 west of Marfa | ≈ 9 per hour | |
| Union Pacific | 0.5 per hour | |
| RM 2810, toward Marfa | ≈ 0.5 per hour | about 1.5 per hour where the inversion brings the section near Marfa into view |
| Texas Pacifico | ≤ 0.08 per hour | |

**Interpretation.**
- With instrumented bearings, about four-fifths of the band where the lights are described sees fewer than one catalogued ordinary light per 100 hours. Seen this way, the binary zone overstated how crowded the view is.
- The quiet share is insensitive to the traffic, haze and detection assumptions, because those move patches between rate bins rather than in or out of the footprint. The two things that do change it are the observer's error box (80% falls to 36% with a hand compass) and whether the Texas Pacifico line runs at night (80% versus 91%).

## Motion signature

For a car at speed *v*, the apparent speed across the view is ω = *v*·|sin *h*| / *d*.

| Road | Median at 100 km/h | 10th–90th percentile |
|---|---|---|
| US-67 | 0.9° per minute | 0.18–1.4 |
| RM 2810 | 0.6° per minute | 0.14–2.0 |
| US-90 west of Marfa | 0.5° per minute | |

At 100 km/h, a US-67 car takes roughly 10 minutes to cross the visible stretch. It blinks out wherever the road dips behind terrain, which matches the visible pieces in Figure 2.

Consequences for identifying lights:
- A light that sits still for minutes on a road's locus is not a moving car. It could still be a parked car or a car turning.
- A light that moves across a road's locus, or faster than about 4° per minute (the upper end even for nearby US-67 at 18 km), is not a car on that road.

## Limits

- **The catalogue is incomplete.** Ranch lights, county and private roads, and unregistered structures are not included, so "quiet" means quiet with respect to catalogued sources.
- **Traffic.** AADT is an annual average. Night traffic around events such as the Marfa Lights Festival will be higher. The per-hour share is the weakest number, so field traffic counts should replace it.
- **Railroads.** The FRA inventory is self-reported and can be out of date. The Presidio–Ojinaga rail bridge is expected to reopen to cross-border service in 2026 (Wikipedia, citing TxDOT). If it does, Texas Pacifico night traffic should be re-checked.
- **Refraction.** The constant-*k* limits of note 2 apply.

## Field use

The script builds a zone for a specific night from measured parameters:

    python analysis/weighted_zone.py --k 0.6 --mor 80 --err-az 0.2 --err-el 0.08 --hourly-share 0.015 --out night.json

- *k* comes from the temperature gradient between two measurement heights (note 2).
- MOR comes from the extinction of a reference star.
- The error box comes from bearings taken on the known lit towers at 230°, 256° and 259° true.
- *s* comes from a traffic count on US-67 during the watch.

## References

- Reagan, I. J., Brumbelow, M. L., Flannagan, M. J., Sullivan, J. M. (2017). High beam headlamp use rates: effects of rurality, proximity of other traffic, and roadway curvature. *Traffic Injury Prevention*. https://www.iihs.org/topics/bibliography/ref/2116
- Sullivan, J. M., Adachi, G., Mefford, M. L., Flannagan, M. J. (2004). High-beam headlamp usage on unlighted rural roadways. *Lighting Research & Technology* 36(1). UMTRI report: https://deepblue.lib.umich.edu/handle/2027.42/55182
- Federal Railroad Administration, U.S. DOT Crossing Inventory Form, FRA F 6180.71 (Part II, item 1: day thru trains 6 AM–6 PM, night thru trains 6 PM–6 AM). https://railroads.dot.gov/sites/fra.dot.gov/files/2020-07/FRA%20F%206180.71.pdf
- TxDOT AADT Annuals (Public View), ArcGIS feature service, retrieved 2026-09-28 (`data/inputs/txdot_aadt.json`).
- FHWA (2018). *Traffic Data Computation Method Pocket Guide*, FHWA-PL-18-027. https://www.fhwa.dot.gov/policyinformation/pubs/pl18027_traffic_data_pocket_guide.pdf
- "Presidio–Ojinaga International Rail Bridge," Wikipedia. https://en.wikipedia.org/wiki/Presidio%E2%80%93Ojinaga_International_Rail_Bridge

Code: `analysis/weighted_zone.py` produces `data/derived/weighted_zone.json` and `docs/data/zos_rate.json`.
