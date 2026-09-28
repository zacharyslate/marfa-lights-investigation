# 4. How bright would a car look? A headlamp photometry model

## Question

A car on a road that is in view is a candidate source only if enough of its light reaches the platform. Headlamps are strongly directional. A car pointing at the Viewing Area can look as bright as the brightest stars. The same car seen 30° off its axis can be invisible. This note computes, for every point of every road in view, how bright a car there would look, given the direction it is pointing.

## Geometry in the car's frame

For a car at distance *d* with heading ψ (the direction of travel, which includes the curve of the road at that point), define:

- **h**: the horizontal angle of the Viewing Area relative to the car's heading, positive to the driver's right.

      h = wrap( β_car→viewer − ψ )

  Here β is the geodesic bearing from the car to the viewer.
- **v**: the vertical angle of the viewer above the lamp axis.

      ε = (E_viewer − E_lamp)/d − d(1−k)/(2R)       viewer's elevation angle as seen from the lamp
      θ = arctan(grade along ψ)                     vehicle pitch on the slope
      v = ε − θ

  Grade is a least-squares slope of DEM road elevation over ±250 m. Going uphill tilts the beam up, so the viewer ends up lower in the beam.

Both travel directions are evaluated. At most one of them faces the viewer (|h| < 90°). Seen from the other direction the car shows only its red tail lamps, and those are **not** modelled here.

Values for the roads in view, with cars heading toward Marfa (the direction that faces the platform):

| Road | h, 10th–50th–90th percentile of the absolute value |
|---|---|
| US-67 | 3.6° – 14.8° – 33° |
| RM 2810 | from −18° to +87° depending on the bend |

On US-67 the straight at **233.5°–233.7° true, 31–33 km out**, points within 3°–5° of the Viewing Area. Northbound cars on that stretch are aimed almost straight at the platform.

## Beam data

There is no public "average U.S. headlamp" intensity table that we could verify. So the model uses **one measured production headlamp**, and treats lamp-to-lamp variation as an uncertainty.

- **Source**: NHTSA compliance test report 108-CAN-17-004, Calcoast-ITL, 30 Nov 2016. It tested a 2016 Ford Focus S left-hand VOR replaceable-bulb headlamp (H11 low beam, H1 high beam), sample LH1, goniometer at 100 ft.
- **Beams**: the upper beam is the FMVSS 108 Table XVIII column UB2; the lower beam is Table XIX-a column LB2V.
- **Values used**: the "Measured" column, before any re-aim. Some key points:

| Beam | Test point (h, v) | Measured cd | FMVSS requirement in the report |
|---|---|---|---|
| Upper | H-V (0, 0) | 55,312 | 40,000 – 75,000 |
| Upper | H-3L / H-3R | 22,738 / 27,569 | ≥ 15,000 |
| Upper | H-6L / H-6R | 11,746 / 10,260 | ≥ 5,000 |
| Upper | H-12L / H-12R | 4,374 / 2,674 | ≥ 1,500 |
| Upper | maximum, 0.9D 0.2R | 75,078 | — |
| Lower | H-V | 5,384 | — |
| Lower | 0.5U 1.5L to L (at 1.7L) | 1,130 (713 after re-aim) | ≤ 1,000 |
| Lower | 0.5U 1.0R to 3.0R (at 2.9R) | 476 (737 after re-aim) | ≥ 500 |
| Lower | 1.5D 2.0R | 32,467 | ≥ 15,000 |
| Lower | H-8L | 1,998 | ≥ 64 |

Two points in the lower-beam rows failed as built and passed only after the re-aim the procedure allows. This shows directly how sensitive the region just above the cut-off is to aim. That region matters here, because the platform sits at v ≈ 0 to +2° for most cars.

## Interpolation

- log₁₀ I is interpolated linearly over the scattered test points, in a space where v is stretched ×4 (vertical gradients are much steeper than horizontal ones).
- Outside the measured region, each row of constant *v* is continued horizontally from its last measured value, with a fall-off of 0.04, 0.07 or 0.12 decades per degree.
  - The 0.07 central value is close to the measured upper-beam fall-off between 9° and 12°: 0.075 dex/° on the left, 0.106 on the right.
- The upper beam is measured only to ±12°, the lower beam to ±20° (at 4° down). **Most US-67 and RM 2810 geometry at |h| > 12–20° is extrapolation.** Figure 3a–b shades those regions.

## From intensity to magnitude

- Two lamps, unresolved: *E* = 2 *I*(h, v) *T* / *d²* (lux).
- Transmission: *T* = exp(−σ*d*) with σ = ln 20 / MOR. The meteorological optical range (MOR) is defined as the path that reduces a collimated beam from a 2,700 K lamp to 5% of its flux (WMO-No. 8; IALA dictionary). The central case uses MOR = 100 km (T = 0.36 at 34 km). This is an assumption for a clear desert night, not a measurement. MOR = 50 km dims a car at 35 km by a further 1.1 magnitudes; MOR = 200 km brightens it by 0.6.
- Apparent magnitude, from Schaefer (1993), who gives *m* = −16.57 − 2.5 log₁₀(*E*/foot-candle). With 1 fc = 10.764 lx:

      m = −13.99 − 2.5 log₁₀(E / lx)              (m = 0 ↔ 2.54 × 10⁻⁶ lx)

- Uncertainty band: the model is re-run with *v* ± 0.5° (aim, load and suspension) and with the three fall-off rates. The band is the minimum and maximum of those runs.
  - The ±0.5° is our assumption, not a regulatory tolerance.
  - The band does **not** include lamp-to-lamp variation (FMVSS allows the upper-beam H-V from 40,000 to 75,000 cd for this lamp type), HID/LED lamps, adaptive or auxiliary lamps, dirty lenses, or trucks.

## Reference values

A lamp pair seen head-on (h = v = 0), MOR 100 km:

| *d* | Low beam | High beam |
|---|---|---|
| 10 km | −3.7 | −6.3 |
| 20 km | −1.9 | −4.4 |
| 30 km | −0.7 | −3.2 |
| 40 km | +0.2 | −2.3 |
| 50 km | +1.1 | −1.5 |

For comparison, Sirius is −1.46, and the typical naked-eye limit at a dark site is about +6 (Schaefer 1993).

## Results (Figure 3c)

**US-67, northbound cars** (278 samples in view or marginal):
- Median predicted magnitude is +0.9 with high beams and +3.0 with low beams.
- About half the samples are brighter than +1 with high beams.
- On the aligned straight at 233.5°–233.7°, high beams reach **−2.2**, brighter than Sirius. Low beams there range from −1.6 to +2.4, depending on aim.

**RM 2810, cars heading toward Marfa** (27 km in view):
- High beams reach −2.2 and low beams −0.3 where bends point at the platform, near 255°–256°.
- The median is +2.0 with high beams and +4.0 with low beams.

**US-90 west of Marfa**, 284°–287° true, 19–27 km, eastbound traffic:
- h ≈ −8°, so the cars appear around −1.7 with high beams and +0.2 with low beams.

**US-67/90 beside the platform:** a car there appears at magnitude −6 to −12.

**Implications for the field programme:**
- Brightness alone cannot separate a car from an "orb". A car on the aligned US-67 straight or on the RM 2810 bends is as bright as the brightest stars.
- A car's brightness should rise and fall in a predictable way as it drives through bends. This is a testable signature: the predicted light curve along the road can be compared with a timed video of a known car.
- Southbound cars on US-67 and cars leaving Marfa on RM 2810 face away from the platform, so they should be seen only as red tail lamps.

## Limitations and what would fix them

1. One lamp model. The fix is to measure real cars from the platform: drive a car of known make along the visible segments at timed intervals and record it with a calibrated camera.
2. DEM road grade is noisy on a ±250 m scale. A few spikes in *v* of ±3° are probably artefacts of cuts and fills. A GNSS track of the road would fix this.
3. Atmospheric transmission uses a fixed MOR. It should be measured on the night, for example from the brightness of a known star near the horizon, or with a visibility sensor.
4. The model does not include scintillation. Turbulence near the ground makes point sources twinkle and change colour, and that is part of how the lights are described.

## References

- NHTSA compliance test report 108-CAN-17-004 (FMVSS No. 108), 2016 Ford Focus S LH VOR replaceable-bulb headlamps, Calcoast-ITL, San Leandro CA, 30 November 2016. https://static.nhtsa.gov/odi/ctr/2017/TRTR-644737-2017-001.pdf
- 49 CFR 571.108, Federal Motor Vehicle Safety Standard No. 108. https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-571/subpart-B/section-571.108
- Schaefer, B. E. (1993). Astronomy and the limits of vision. *Vistas in Astronomy* 36, 311–361. doi:10.1016/0083-6656(93)90113-X
- World Meteorological Organization, *Guide to Instruments and Methods of Observation* (WMO-No. 8), chapter on visibility (MOR definition). https://library.wmo.int/records/item/41650-guide-to-instruments-and-methods-of-observation
- IALA, *International Dictionary of Marine Aids to Navigation*, "Meteorological Optical Range". https://www.iala.int/wiki/dictionary/index.php/Meteorological_Optical_Range

Code: `analysis/headlight_model.py` produces `data/derived/headlights.json`.
