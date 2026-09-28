# 5. The Zone of Skepticism

> **Superseded numbers (2026-09-28).** This working note describes the v1 model. The line-of-sight model has since been rebuilt (exact WGS84 geometry, 1 m lidar terrain with point-cloud obstructions, Monte Carlo classes, height-dependent ray tracing); see [note 11](11_model_v2_methods.md) for the current methods and numbers, and [note 12](12_experimental_design.md) for the planned experiments. Where this note and note 11 disagree, note 11 is correct.

> This note defines the **binary** zone: where a catalogued light *can* appear. The binary version treats a nearly idle railroad the same as a highway. Note 8 weights each source by how often it actually produces a light, and that weighted version supersedes this one for field use.

## Definition

The **Zone of Skepticism (ZoS)** is the set of apparent positions, in true bearing and elevation angle as seen from the Viewing Area, where a **catalogued ordinary light source** could appear, once refraction and the observer's own measurement error are allowed for.

- A light reported **inside** the ZoS has at least one mundane candidate. That candidate has to be ruled out before the light is treated as unexplained, using timing, motion, colour, spectrum or a second observer.
- A light **outside** the ZoS and below the skyline has no catalogued candidate. This is where attention should go first. It is not evidence of anything unusual: the catalogue is incomplete (see "Not in the zone").

The ZoS is the first filter in the field protocol, which aims to raise signal to noise by removing false positives before studying the remainder.

## Construction

1. **Sources.** Each catalogued source *i* has true bearing *a_i*, range *d_i*, apparent elevation α_i(0.13) and critical refraction coefficient k_crit,i (notes 2 and 3). The sources are:
   - **Roads.** US-67 at 60 m spacing, plus the TxDOT state roads in the fan at 120 m spacing: RM 2810, US-90, US-67/90 beside the platform, FM 170, SH 118, RM 169, FM 1112 and SH 17. Lamp height 0.7 m.
   - **Railroads.** Union Pacific and Texas Pacifico, with a 4 m locomotive headlamp.
   - **Lit towers.** FCC Antenna Structure Registrations whose registered lighting is not "none"; the top light is used.
   - **Towns.** Direct light if the town is in view for some k ≤ 1. Otherwise a skyglow band from the skyline up to +0.5°, over ±1° of bearing.
   - **The tethered aerostat** (TARS site at 292.9° true). It is a full-height column, because its altitude varies.
2. **Refraction range.** A source counts if it is in view anywhere in 0 ≤ k ≤ 1, that is, if k_crit,i ≤ 1. Its locus is the vertical segment

       [ α_i(max(k_crit,i, 0)),  α_i(1) ],   α_i(k) = α_i(0.13) + d_i (k − 0.13) / (2R)

3. **Continuity.** Neighbouring samples of the same road or track that are less than 1 km apart on the ground are joined, because a car moves continuously between them.
4. **Observer error.** Each segment is widened by the observer's measurement uncertainty. There are two tiers:

   | Tier | Observer | Bearing | Elevation |
   |---|---|---|---|
   | A | instrumented: a photo or video with the skyline in frame, or a theodolite | ±0.3° | ±0.1° |
   | B | hand compass, with elevation judged against the skyline | ±3° | ±0.25° |

   The values are working assumptions and should be replaced by errors measured in the field. For example, an observer can take bearings on known towers and on a car at a known position.
5. The union is rasterised at 0.02° × 0.04 mrad and converted to polygons. The outputs are `data/derived/zos.json` and `docs/data/zos.json`.

## Results

Coverage is measured inside the 120° fan (157.3°–277.3° true):

| | Tier A | Tier B |
|---|---|---|
| Share of the view from −12 mrad (−0.69°) up to the skyline | 24% | 66% |
| Share of the 5 mrad (0.29°) band just below the skyline | 33% | 74% |

- The lower limit of −12 mrad is a descriptive choice, and the percentages depend on it.
- The band just below the skyline is where Bunnell's camera stations describe the lights: above the brush but below the mesas (Bunnell 2009, as summarised in the website's sources).

**Main message: measurement quality decides how much of the sky can be tested.**
- With hand-compass bearings, about three-quarters of the band where the lights are reported falls inside the zone. A light seen there cannot be separated from ordinary sources.
- Instrumented bearings shrink that share to about a third.
- The field protocol should therefore require a skyline-referenced photograph for every candidate.

Where the zone lies (Figure 2):

| Source | True bearing | Distance | Notes |
|---|---|---|---|
| US-67 | 228.7°–252.1° | 24–40 km for the visible part | core zone |
| RM 2810 | 252.9°–274.4° | 32–53 km | newly identified; just below the skyline in the Chinati foothills |
| Texas Pacifico track | 143°–213° | 3.8–8.1 km | the only track in view in this arc |
| Lit towers | 230.3° (89 m), 255.7° (106 m), 259.2° (82 m, above the skyline), 279.7°, 284.2° | | |
| US-90 and Union Pacific, Marfa and its skyglow | 280°–289° | | |
| Aerostat | 292.9° | | |
| Presidio / Ojinaga skyglow | 210°–214° | | |
| Shafter skyglow | about 219° | | |

The largest open sectors are the bearings where tier A covers less than 5% of the view below the skyline:

- **261°–274°**, west of RM 2810
- **239°–251°**, between US-67 and RM 2810
- **220°–228°**, south of the visible US-67

Tier B still covers parts of all three.

## Not in the zone, and why that matters

The zone leaves out:
- ranch yard lights and security lights;
- vehicles on private ranch roads and county roads outside the TxDOT state system;
- unregistered structures;
- fires;
- aircraft, satellites and astronomical sources. These are all above the skyline, except aircraft on approach and very low bodies setting.

Mirage conditions (k well outside 0–1, ducting, looming) can place any source outside its computed zone. A light outside the ZoS is therefore a **candidate** for further study, not an anomaly. The next catalogue work should be:
1. Ranch lights, mapped from night imagery, for example VIIRS Day/Night Band composites.
2. County roads, from TIGER/Line.

## Reference

- Bunnell, J. (2009). *Hunting Marfa Lights*. Lacey Publishing. ISBN 978-0970924940. Self-published and not peer reviewed.

Code: `analysis/zone_of_skepticism.py`.
