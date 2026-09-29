# 4. How bright would a car look? Photometry v2 (2026-09-29)

This note replaces the v1 headlamp note, which used one production lamp (a 2016 Ford Focus compliance test) and the v1 line-of-sight model. Code: `analysis/marfa/photometry.py` (physics and lamp data), `analysis/marfa/run_photometry.py` (all roads), `analysis/marfa/run_traffic.py` (one car over time, occupancy), `analysis/headlight_model.py` (site export). Tests: `analysis/tests/test_photometry.py` (8 tests). Results: `data/derived/los2/photometry.{npz,json}`, `traffic_us67.json`. Figures 3 and 8.

## Question

A car on a road in view is a candidate source only if enough of its light reaches the platform. Lamps are strongly directional, so the answer depends on where the Viewing Area falls in the car's own beam, and that changes with every bend and grade of the road.

## Geometry in the lamp's frame

For each road sample (60 m spacing) and each direction of travel:

- **h**, horizontal angle of the viewer off the car's heading, positive to the driver's right: h = wrap(β_car→viewer − ψ). The heading ψ comes from the neighbouring samples along the TxDOT centreline.
- **v**, vertical angle of the viewer above the lamp axis: v = ε_T − θ − a.
  - ε_T is the elevation of the arriving ray at the lamp above the lamp's own horizontal. From the exact chord geometry of the line-of-sight model (note 11): ε_T = −e_O − D/R + kD/(2R), where e_O is the chord elevation at the eye, D the chord length and R the normal-section radius. (For equal heights and no refraction both ends see the chord at −D/2R, which is one of the unit tests.)
  - θ = arctan(grade) is the vehicle pitch. The grade is taken from the 1 m lidar at ±25 m along the heading (v1 used a ±250 m fit to the 1″ DEM, which smoothed away the grade changes that matter).
  - a is the vertical aim error, 0 in the central case and ±0.5° in the bands.

The lamps are 1–1.5 m apart, which is 8–17″ at 18–40 km: one unresolved point to the naked eye.

**Result for US-67 (Shafter–Marfa, road in view).** The road runs almost straight at the platform. Northbound cars (toward Marfa) have the viewer only 3–33° to the driver's right (median 14°), at v from −0.6° to +2.5° (median +0.8°). Southbound cars show their rear, 3–33° off the rear axis. The median |grade| is 1.6%, 95th percentile 4.7%, so pitch changes v by up to ±2.7°, as much as the geometry itself.

## Lamp data

| Lamp | Source | Values used |
|---|---|---|
| Low beam | Schoettle, Sivak, Flannagan & Kosmatka (2004), UMTRI-2004-23, Table 4: market-weighted over the 20 best-selling U.S. model-year-2004 vehicles | 25th/50th/75th percentile intensity (cd) on a grid 45L–45R × 5D–7U; H-V median 8830 cd (quartiles 5758–11846) |
| High beam | Schoettle, Sivak & Flannagan (2001), UMTRI-2001-19, Table 6 (U.S.) | same grid; H-V median 37005 cd |
| Tail, stop, high-mounted stop | FMVSS No. 108 photometry as tabulated in NHTSA TP-108-13 | tail 2.0 cd min at H-V, 0.8 at 10°, 0.3 at 20°, max 18; stop 80/40/10 min, max 300; high-mounted stop 25/16 min, max 160 |
| Wide angles (>45°) | none | intensity held at its 45° value ('hold'), or the regulatory floor of the front position and side-marker lamps ('floor') |

Interpolation is linear in log I on the UMTRI grid. Every one of the 1125 cells of both tables satisfies p25 ≤ p50 ≤ p75. The values were read from the PDF text layer and checked cell by cell; a web summariser had returned wrong right-side values, so only parsed numbers are used.

No market-weighted data were found for signal lamps, so rear lamps are bracketed between the regulatory minimum and maximum. Beyond the last tabulated angle the minimum is held at that angle's value out to 45° and set to zero beyond (conservative for visibility).

## From intensity to magnitude

    E = Σ I_i T / D²,   T = exp(−ln 20 · D / MOR)        (lux; MOR = distance at 5 % transmission)
    m = −13.99 − 2.5 log10(E / 1 lx)                      (Schaefer 1993)

The National Park Service reports standard visual range (SVR) for Big Bend: about 90 mi on average, below about 55 mi on high-pollution days, about 165 mi without pollution. SVR is the Koschmieder range for a 2% contrast threshold, 3.912/b_ext, whereas MOR is defined by 5% transmission, ln 20/b_ext, so MOR = 0.766 SVR. The runs use MOR = 68, 111 (reference) and 203 km. (A first version of this note used the SVR values directly as MOR, which made cars about 0.2 mag too bright at 30 km.)

## Detection threshold

Naked-eye limiting magnitude for a point source on a background of surface brightness μ (mag arcsec⁻²), Crumey (2014, eq. 54, valid for 20 < μ < 22):

    m_lim = 0.3834 μ − 1.4400 − 2.5 log10 F

F is the observer's field factor (Crumey: typically 1.4–2.4). The runs span μ = 20.5–22 and F = 1.4–4, giving m_lim = 4.9–6.6. Reference: μ = 21, F = 2, m_lim = 5.86. μ near the horizon at Marfa has not been measured; the bracket is wide for that reason.

## Results for US-67 between Shafter and Marfa (k = 0.13, MOR 111 km)

"In view" means P_vis ≥ 0.5 for that lamp's height: headlamps 0.66 m, rear lamps 0.86 m, high-mounted stop lamp 1.12 m.

| Direction, lamps | Road in view | Magnitude, median (range) | Detectable, reference | Detectable, full bracket* |
|---|---|---|---|---|
| Northbound, low beam, market median | 10.0 km | 2.6 (−1.7 to 6.0) | 9.6 km | 9.0–10.0 km |
| Northbound, low beam, 25th / 75th pct lamp | 10.0 km | 2.9 / 2.2 | 9.4 / 10.0 km | 8.7–10.0 / 9.1–10.0 km |
| Northbound, high beam, median | 10.0 km | 0.4 (−2.4 to 5.4) | 10.0 km | 9.3–10.0 km |
| Southbound, tail lamps at FMVSS minimum | 10.1 km | 9.1 (7.9 to 10.6) | 0 | 0 |
| Southbound, tail lamps at FMVSS maximum | 10.1 km | 5.6 (4.7 to 6.3) | 6.7 km | 0–10.1 km |
| Southbound, braking, FMVSS minimum | 10.1 km | 4.6 (3.7 to 6.1) | 9.4 km | 4.4–10.1 km |
| Southbound, braking, FMVSS maximum | 10.1 km | 2.2 (1.4 to 2.9) | 10.1 km | 10.1 km |

*Least favourable = MOR 68 km, μ = 20.5, F = 4; most favourable = MOR 203 km, μ = 22, F = 1.4.

**What this means.**

1. **Headlamps.** A northbound car is a naked-eye light over at least 87% of the road in view under every combination of lamp, haze and observer tried, and over 93% at the reference values. Typically it is a light of magnitude 2–3; on the straight at 233.6°–233.8° (31–33 km, heading within a few degrees of the platform) it reaches magnitude −1.7 on low beam and −2.4 on high beam, brighter than Sirius (−1.46).
2. **Brightness is not steady.** Within one window the brightness changes by a median 1.1 mag (up to 4.9 mag); between successive 60 m samples (2 s at 30 m/s) the change exceeds 0.8 mag one time in ten (max 2.7 mag). The causes are grade, which pitches the beam by degrees (the viewer sits near the top of the low beam, v ≈ 0 to +2.5°, where intensity falls by a factor of about 2 per degree, median), and curves, which swing h. The model predicts lights that brighten and fade without any change in the car. (An earlier draft said "tenfold per degree"; the UMTRI table gives ×1.4–2.3 per degree at the observer positions, interquartile.)
3. **Tail lamps** are the least constrained part. At the regulatory minimum they are invisible (m ≈ 8–10.6). At the maximum they sit right at the threshold (m ≈ 5.6). Braking brings them to m ≈ 4.6 even at the minimum. Market data would narrow this.
4. **Colour.** Headlamps are white; tail and stop lamps are red. A red light moving away along the US-67 bearings is the tail-lamp case, and it is faint.
5. **RM 2810** (12.9 km in view): only the direction toward Marfa faces the viewer (|h| 3–42°, median 18°). Low-beam median m = 4.0, brightest −0.7; high beam brightest −2.4 (MOR 111 km).
6. **v1 comparison.** v1 predicted about −2 on high beam at 233.7°. v2 agrees on the brightest spot (−2.4 at 233.8°) and adds that the typical northbound car is m ≈ 2–3, that detection is robust to haze and lamp type, and the tail-lamp bracket.

## One car, and how many at once (Figure 8)

A northbound car at 30 m/s (the speed measured in the photographs, note 9) crosses the in-view region in 13.6 min. It is in view for 334 s, in **18 separate windows**: median 510 m of road (17 s), from 60 m (2 s, the sampling limit) to 2.1 km (70 s). It moves across the view at about 0.9° per minute (90th percentile 1.2°/min), always below the skyline by 0.04–0.84° (median 0.26°). So one car produces a light that appears, drifts, brightens and fades, vanishes, and reappears a little further along, 18 times.

Southbound cars give the same windows in reverse order (tail lamps).

**Occupancy.** For a one-way flow q (vehicles per hour) the number of cars in view has mean N = q L / u, with L = 10.0 km of road in view. At 30 m/s, N = 0.93 per 10 vehicles per hour in each direction. The 2025 AADT at the two stations on this segment is 1121 and 1383 (both directions), a daily-mean one-way flow of 23–29 vehicles per hour. At that mean flow about 2–3 northbound cars would be in view at any moment. Night flows are lower, but no hourly count for this road was found; this is the number a field count must supply.

## Limitations

1. **Fleet age.** The UMTRI tables describe model-year-2004 low beams and circa-2000 high beams. Today's LED lamps have sharper cut-offs and different wide-angle light; the 25–75% band does not cover this. A current market-weighted table, or measurements of cars from the platform, would.
2. **Wide angles and signal lamps** are bracketed, not modelled.
3. **Pitch.** Grade from the lidar at ±25 m approximates vehicle pitch; suspension and load add a pitch the ±0.5° aim band only partly covers.
4. **Threshold.** μ at the horizon, and the observer's F, are not known for Marfa. The lights near the threshold (tail lamps, the 5.7 low-beam minimum) depend on them; the headlamp conclusion does not.
5. **Colour and scintillation** are not modelled. The magnitudes are photometric (V-like). Turbulence near the ground makes point sources twinkle and change colour.
6. **Sampling.** Windows shorter than 60 m cannot be resolved.

## References

- Schoettle, B., Sivak, M., Flannagan, M. J., Kosmatka, W. J. (2004). *A market-weighted description of low-beam headlighting patterns in the U.S.: 2004.* Report UMTRI-2004-23, University of Michigan Transportation Research Institute. https://deepblue.lib.umich.edu/bitstreams/f1d0eb69-093d-4e54-9785-865477c8b1b6/download
- Schoettle, B., Sivak, M., Flannagan, M. J. (2001). *High-beam and low-beam headlighting patterns in the U.S. and Europe at the turn of the millennium.* Report UMTRI-2001-19. https://deepblue.lib.umich.edu/handle/2027.42/49446
- NHTSA, *Laboratory Test Procedure for FMVSS 108, Lamps, Reflective Devices and Associated Equipment*, TP-108-13 (draft, 4 December 2007). https://www.nhtsa.gov/sites/nhtsa.gov/files/tp-108-13.pdf
- 49 CFR 571.108, Federal Motor Vehicle Safety Standard No. 108.
- Schaefer, B. E. (1993). Astronomy and the limits of vision. *Vistas in Astronomy* 36, 311–361. doi:10.1016/0083-6656(93)90113-X
- Crumey, A. (2014). Human contrast threshold and astronomical visibility. *Monthly Notices of the Royal Astronomical Society* 442(3), 2600–2619. doi:10.1093/mnras/stu992
- National Park Service, *Park Air Profiles – Big Bend National Park*. https://www.nps.gov/articles/airprofiles-bibe.htm
- World Meteorological Organization, *Guide to Instruments and Methods of Observation* (WMO-No. 8), visibility chapter (MOR definition).
- TxDOT AADT Annuals (2025), stations 189D5 and 189H5A.
