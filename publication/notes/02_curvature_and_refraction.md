# 2. Earth curvature and atmospheric refraction

## Curvature drop

Take a horizontal line from the eye and go a distance *d* along it. The Earth's surface (radius *R* = 6,371 km) falls away below that line by

    h_c = d² / (2R)

This is the leading term of the exact height of the tangent line above the sphere, R(sec(d/R) − 1) = d²/(2R) + 5d⁴/(24R³) + …, so the approximation error grows as d⁴: about 0.2 mm at 21 km, 1.2 mm at 35 km, 5 mm at 50 km and 8 cm at 100 km. Example values: 34.6 m at 21 km, 96.1 m at 35 km, 196.2 m at 50 km.

The Earth is not a sphere. At Marfa's latitude (30.3° N) the WGS84 ellipsoid's radius of curvature is 6,351 km north–south and 6,383 km east–west; along the sightlines toward the south-west (azimuth ~225°) it is 6,367 km (Euler's formula). The line-of-sight model (analysis/marfa) does not use h_c at all: it places the eye, the lamp and every terrain sample in Earth-centred coordinates on the WGS84 ellipsoid (heights converted from NAVD88 with the GEOID18 grid) and measures heights relative to the straight chord between eye and lamp, so Earth curvature enters exactly. The formula above is kept here because it explains the size of the effect.

## Refraction coefficient k

Air density drops with height, so a nearly horizontal light ray bends slightly downward, toward the ground. The **refraction coefficient** *k* is the ratio of the Earth's radius to the ray's radius of curvature. A ray that curves downward partly follows the curve of the Earth, so the apparent drop becomes

    h_{c+r} = d² (1 − k) / (2R)

Equivalently, the Earth behaves as if its radius were R/(1 − k). Surveyors conventionally use k = 0.13 for daytime paths well above the ground.

Near the ground, *k* is set mainly by the vertical temperature gradient. Hirt et al. (2010) give the standard relation

    k = 503 · (P / T²) · (0.0343 + dT/dz)        P in hPa, T in K, dT/dz in K/m

At the Viewing Area (about 1,494 m), take P ≈ 850 hPa and a night-time T ≈ 283 K. Then 503·P/T² ≈ 5.34, which gives:

| dT/dz (K/m) | Condition | k |
|---|---|---|
| −0.0065 | standard lapse rate | 0.15 |
| 0 | isothermal | 0.18 |
| +0.05 | moderate inversion | 0.45 |
| +0.153 | strong surface inversion; k = 1, ray curvature equals the Earth's | 1.00 |
| +0.30 | very strong inversion close to the ground | 1.78 |
| −0.2 | daytime superadiabatic layer | −0.9 |

Hirt et al. measured *k* at 1.8 m above ground over a whole day and found values from about −4 at midday to +16 around sunset. Clear, calm nights over Mitchell Flat favour strong surface inversions, so *k* well above 0.13 should be expected there.

## Apparent elevation angle

A lamp of height *h* above ground *z_t*, seen from the eye at height *E*, appears at elevation angle

    α ≈ (z_t + h − E)/d − d(1 − k)/(2R)            (radians; small-angle form)

Changing *k* by Δk shifts the apparent elevation by

    Δα = d Δk / (2R)

At 35 km, Δk = 1 gives 2.75 mrad (0.16°). **Figure 5b** plots this. The practical point is that ordinary refraction moves distant lights by a few tenths of a degree at most. Hand estimates of elevation are much coarser than that.

## Why humidity is not in the bending model

In the visible spectrum, water vapour changes the refractive index of air far less than temperature and pressure do (Ciddor 1996). So humidity has almost no effect on bending. It does matter for **extinction** (haze), which the brightness model handles through the meteorological optical range (note 4).

## Limits of a constant *k*

- The model applies one *k* to the whole path. Real night inversions are strongest in the lowest few metres and weaken with height. A grazing ray therefore sees a *k* that changes along its path.
- Strong gradients produce mirages: superior mirages, looming, towering and ducting. Their images can be inverted, stretched or multiple, and a constant *k* cannot represent them.
- The Zone of Skepticism (note 5) is computed for 0 ≤ k ≤ 1, so it does not cover mirage conditions.
- The planned next step is a layered ray trace driven by a measured temperature profile. The field campaign should log temperatures at 0.5 m, 2 m and, if possible, about 10 m.

## References

- Hirt, C., Guillaume, S., Wisbar, A., Bürki, B., Sternberg, H. (2010). Monitoring of the refraction coefficient in the lower atmosphere using a controlled setup of simultaneous reciprocal vertical angle measurements. *J. Geophys. Res.* 115, D21102. doi:10.1029/2010JD014067
- Ciddor, P. E. (1996). Refractive index of air: new equations for the visible and near infrared. *Applied Optics* 35(9), 1566–1573. doi:10.1364/AO.35.001566
