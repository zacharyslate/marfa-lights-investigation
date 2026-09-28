# 12. Experimental design (draft for pre-registration)

**Status:** draft, 2026-09-28. Field dates, equipment and permissions are to be confirmed by the author.

**Purpose.** The model (note 11) makes quantitative, falsifiable predictions: which stretches of road are visible from the platform, the apparent direction and elevation of a lamp there, and how both change with the night-time temperature structure. The experiments below test those predictions directly, and then use the tested model as a filter. Lights the model explains (vehicles, aircraft, fixed lights, astronomical objects and their refracted images) are removed, and only the residue is studied as candidate anomalies.

**Ordering.** Each experiment removes one named source of uncertainty identified in note 11. They are ordered so that the cheapest measurements come first and every later experiment relies on the earlier ones.

## E1. Observer geometry and camera calibration (1 evening)

**Uncertainty addressed.** The eye position and height are the largest geometric input that has not been measured. The lidar shows a platform about 1.4 m above the surrounding ground; the model assumes an eye 1.6 m above the platform, with σ 0.15 m.

**Procedure.**
- Survey the standing positions along the platform wall with GNSS. RTK, or static PPP of at least 2 h, reported in NAD83(2011) with ellipsoidal heights.
- Measure the actual eye heights of the observers.
- Photograph the south-western horizon at dusk and after dark with a calibrated camera. Use RAW files, a fixed focal length, and lens distortion measured on a star field.
- Plate-solve the star frames to get absolute pointing (azimuth, elevation, roll) independently of the terrain model.

**Test.** Measured skyline elevation against the model skyline (k = 0.13 at dusk, and the E2 values at night), over azimuth 215–285°.
- Pre-registered criterion: RMS residual ≤ 0.02° over the 10–45 km ridges.
- Residuals are expected to be dominated by refraction at night, which makes the skyline a refraction gauge.

This breaks the circularity of the 2018 photo registration (note 09), in which the camera pointing was fitted to the same terrain model it was then used to test.

## E2. Near-ground refraction (continuous during all nights)

**Uncertainty addressed.** Refraction is the dominant remaining uncertainty. With the constant-k model, visible US-67 ranges from 9.7 km (k = 0) to 11.6 km (k = 1). The ray-traced night profiles move lamps up by as much as 7.5 arcmin, and an elevated inversion can create multiple images. The actual profile over the Marfa plateau has not been measured.

**Instruments.**
- (a) A temperature mast at the platform, with aspirated or radiation-shielded sensors at 0.5, 1, 2, 5 and 10 m, logging every minute. The difference between levels gives dT/dz, which gives k(z, t) through k = 503·P/T²·(0.0343 + dT/dz) (Hirt et al. 2010).
- (b) Where the landowner allows, a second mast in the 8–9 km band that nearly every visible sightline crosses (note 11 §5).
- (c) Several evenings of vertical profiles to 100 m by tethered balloon or drone, to test for elevated inversions (the `cap_40m` scenario).
- (d) A direct optical measurement of refraction. Repeatedly measure the apparent elevation of a few fixed, surveyed light sources at 10–40 km (for example tower obstruction lights at known ASR positions) with the calibrated camera of E1. The difference from the geometric elevation, divided by D/2R, gives k integrated along that path, independently of the mast.

**Test.** The ray tracer, run with the measured profiles, must reproduce the fixed-light elevations within their measurement error. Pre-registered criterion: median |residual| ≤ 0.5 arcmin.

## E3. Controlled vehicle runs (the key test; 2–3 nights)

**Question.** Does a known vehicle appear when and where the model says it will?

**Vehicle.** A test vehicle with a 10 Hz GNSS logger, known lamp heights (measured) and a recorded lamp state (low beam, high beam, DRL, brake) drives US-67 between Marfa and Shafter in both directions. Speeds are legal, and there are several passes per night.

**Blinding.** The observers at the platform do not know the schedule or direction. They log every light they see: time from a synchronised GNSS clock, azimuth and elevation from a camera or theodolite reticle, colour, and a confidence rating. A separate camera records continuously.

**Predictions (made before the runs, from the model with that night's measured refraction).** For every second of every pass:
- P(visible);
- the predicted azimuth and apparent elevation;
- the predicted brightness band.

**Scoring.**
- Detection: Brier score and ROC (area under the curve) of P(visible) against the observed detection.
- Position: residuals in azimuth and elevation for matched sightings.
- Ambiguity: the rate at which the test vehicle is confused with other traffic, resolved with E4.

**Pre-registered success criteria.**
- AUC ≥ 0.85.
- Brier score at least 0.1 below that of a model which predicts every point on the road as visible.
- Median azimuth residual ≤ 0.1°; median elevation residual ≤ 2 arcmin after the E2 correction.

**Sample size.** About 6 passes per night × 3 nights × 90 min per pass, at 1 Hz. The visible stretches total about 10 km, so at 25 m/s each pass spends about 400 s in view and about 5000 s hidden. Roughly 10⁴–10⁵ one-second samples are strongly correlated within a pass, so the unit for inference is the visible stretch crossed during a pass (about 29 stretches × 18 passes ≈ 500 crossings). That is enough to estimate a detection probability per stretch to about ±0.1 (binomial, n ≈ 18 per stretch).

## E4. Traffic and aircraft census (all nights)

**Question.** Which lights at a given moment are ordinary traffic, so that a candidate anomaly can be declared only when no vehicle or aircraft explains it?

**Procedure.**
- Roadside time-stamped cameras (or a counter) near Shafter and at the Marfa end record every vehicle's entry and exit times on US-67.
- Combined with the model, they predict when a vehicle should be in each visible stretch.
- An ADS-B/MLAT receiver at the platform logs aircraft positions.
- Aircraft without transponders (some general aviation) remain a known gap. A dual-station sighting (E5) can still place them.

**Analysis.** Occupancy is modelled as traffic flow × dwell time in each visible stretch. Each observed light is then classed as road-explained, aircraft-explained, fixed-light-explained or unexplained.

## E5. Two-station triangulation (as often as possible)

**Setup.** A second calibrated camera station 3–10 km from the platform, placed roughly perpendicular to the main sightlines (for example on US-90 east of the viewing area, subject to access). Clocks are synchronised by GNSS.

**Measurement.** Any light recorded by both stations is triangulated in three dimensions.
- For a light 30 km away, a 5 km baseline and 0.02° pointing accuracy, the range error is roughly D²·σ/b ≈ 30000² × 3.5e-4 / 5000 ≈ 60 m.
- That is enough to put a light on or off a road.

This is the decisive test for any "unexplained" light: a vehicle is on a road, an aircraft is in the air, and anything else becomes a genuine candidate anomaly.

## E6. Calibrated photometry and colour (all nights)

**Procedure.**
- RAW frames from both stations are calibrated on standard stars at similar elevation angles, which also absorbs the atmospheric extinction near the horizon.
- The output is apparent magnitudes and colour indices of every light.
- These test the headlamp and taillamp brightness model: where the viewer lies in the beam, whether lamps are red or white, and how brightness depends on range.
- They also test the detection limit near the horizon under the measured sky brightness (using an SQM meter at the horizon, or the calibrated frames).

## Pre-registration and analysis rules

The following will be deposited (for example on OSF) before the first field night:
- the hypotheses;
- the model version (a git commit hash);
- all thresholds above;
- the rules for declaring a light "unexplained".

**Rules for "unexplained".** A light is unexplained only if, at its time and direction, ALL of the following hold:
- no vehicle is predicted in any visible stretch within 0.3° of it (E3/E4 model);
- no ADS-B aircraft lies within 0.5°;
- no catalogued fixed light (towers, ranches, towns, lit infrastructure) lies within 0.3°;
- no astronomical object (star, planet, satellite, Moon) lies within 0.3°;
- no ray-traced image of any of the above lies within 0.3° under that night's measured profile.

Only unexplained lights go on to detailed study (E5 triangulation, E6 photometry). The count of unexplained lights, with its uncertainty, is reported whatever it turns out to be, including zero.

## Equipment (indicative; to be costed)

- **Cameras:** two cameras with fixed lenses (35–85 mm) that shoot RAW, with tripods and a GNSS time source.
- **Positioning:** a GNSS receiver capable of RTK or PPP.
- **Temperature:** 5–10 radiation-shielded temperature sensors, and a 10 m mast.
- **Profiling:** a tethered balloon or drone for profiles, permits permitting.
- **Aircraft:** an ADS-B receiver (RTL-SDR class).
- **Test vehicle:** a 10 Hz GNSS logger.
- **Sky brightness:** an SQM meter.

## Open decisions for the author

- **Field window.** New Moon nights are preferred. Seasonal contrast is desirable: winter gives strong surface inversions, summer weaker ones.
- **Access and permissions.** Private land is needed for the second mast and the second camera station; TxDOT/DPS should be notified about the test-vehicle runs.
- **Pre-registration venue**, and whether to recruit independent observers.
