# 13 · Equation check (2026-09-29)

Every equation in the manuscript (`publication/manuscript/marfa_ajp.tex`) and the supplementary material (`marfa_ajp_SI.tex`) was re-derived and tested numerically.

- The tests are in `analysis/tests/test_equations.py`: 15 tests, written independently of the model code, which then check that the code implements the same relation.
- All 45 tests of the project pass.

## Main paper

| Eq. | Formula | How it was checked | Result |
|---|---|---|---|
| 1 | Δh = (1−k) d²/2R; horizon √(2R h_e/(1−k)) | Compared with the exact sphere, R(sec θ − 1), minus the lift of a ray of curvature k/R. | Correct. 61.45 m at 30 km; horizon 4.84 km for a 1.6 m eye. |
| — | Midpoint sag kD²/8R | Direct evaluation. | 2.30 m at 30 km, k = 0.13. |
| 2 | σ = k s(D−s)/2R | Compared with the exact circle of radius R/k through both end points. | Error < (D/R)² relative. The launch angle equals kD/2R. |
| 3 | k_crit = maxᵢ 2R yᵢ / [sᵢ(D−sᵢ)] | Brute force on random terrain, just below and just above k_crit. | Correct. |
| 4 | k = 503 P/T² (0.0343 + dT/dz) | Derived from n − 1 = cP/T with hydrostatic P. Compared with a numerical dn/dz for linear-T atmospheres. | Correct within 0.4% for dT/dz from −0.0098 to 1 K/m. |
| 5 | y'' = −k(a)/R, and the k_max bound | Numerical rays with random k(s) ≤ k_max. | Every ray that reaches the lamp lies below the constant-k_max arc (convexity argument confirmed). |
| 6 | v = ε_Q − arctan g − δ_aim; ε_Q = −e_O − D/R + kD/2R | Exact 3-D geometry on a sphere, 50 random eye–lamp pairs. Pitch sign checked separately. | The exact identity is e_Q = −e_O − γ. Replacing the central angle γ by D/R errs by < 1″. |
| 7 | E = Σ I T / D², T = exp(−D ln20 / V) | Definition of optical range. Standard visual range is 3.912/b (2% contrast). | V = 0.766 × visual range, so 55, 90 and 165 mi become 68, 111 and 203 km. |
| 8 | m = −13.99 − 2.5 log₁₀ E(lx) | Schaefer's foot-candle form, −16.57 − 2.5 log E(fc), with 1 fc = 10.764 lx. The Sun (V = −26.74) gives 1.27 × 10⁵ lx. | Correct. m = 0 corresponds to 2.54 × 10⁻⁶ lx. The worked example gives 2.97 × 10⁻⁷ lx and m = +2.33. |
| 9 | m_lim = 0.3834 μ − 1.4400 − 2.5 log₁₀ F | Coefficients read from Crumey (2014), eq. 54, earlier in the project. Values recomputed. | 5.86 (μ = 21, F = 2); range 4.9–6.6. |
| 10 | N = qL/u | Simulation of Poisson traffic. | Mean and variance equal qL/u; P(at least one car) = 1 − e^−N. 0.928 per 10 vehicles/h. |
| — | Angular drift ω = u \|sin h\| / d | Finite difference. | 0.83°/min for u = 30 m/s, d = 30 km, h = 14°. |

## Supplementary material

- **Euler normal-section radius.** Checked against the meridional and prime-vertical radii.
- **AR(1) error field.** Correlation φ^m = e^(−mΔ/ℓ). Linear interpolation lowers the variance midway between nodes to (1+φ)/2, which is 0.89 at Δ = ℓ/4 (standard deviation −6%).
  - The code docstring said "0.94" for the variance. It now says 0.89 for the variance and −6% for the standard deviation. The code itself was already right: it rescales exactly.
- **Semivariogram model.** γ(r) = σ²(1 − e^(−r/ℓ)) is the semivariogram of a field with correlation e^(−r/ℓ). It matches the fit in `dem_error.py` (sill σ², half-squared differences).
- **Median test.** For 8 values, "median ≤ x" implies "at least 4 ≤ x". So the Poisson-binomial p = 3 × 10⁻⁶ is an upper bound on the chance of a median as small as the one observed. It was confirmed by simulation, and this is now stated in the SI.

## Changes made to the text

1. **Notation clashes removed.**
   - The lamp point T became **Q**, because T is also temperature in Eq. 4. The geometry figure is regenerated with the new label.
   - The aim error a became **δ_aim**, because a is also the height of the ray above the ground in Eq. 5. Its sign is now stated: positive when the lamp is aimed high.
   - The eye height in the horizon formula became **h_e**, because h is also the horizontal beam angle.
   - In the SI:
     - the grid spacing became **Δ**, since g is the grade;
     - gravity became **g₀**;
     - the ellipsoid radii became **R_M, R_N**, since N is the geoid undulation;
     - the variogram lag became **r**.
2. **ε_Q (Eq. 6).** The text now explains the D/R term: it is the angle between the verticals at the eye and the lamp. It also gives the size of the approximation (< 1″).
3. **Hirt constant (SI §S4).** The SI now states that g₀/R_d = 0.0342 K/m while Hirt et al. give 0.0343 (effect on k < 0.001), and that Rc = 503.
4. **Test counts.** The SI and the main text now say 45 unit tests.

## Not changed, with the reason

- **k is defined with a spherical R = 6371 km inside the constant 503, while the sag uses the normal-section radius (6.37–6.38 × 10⁶ m).** The difference is 0.2% in k, which is negligible.
- **Magnitudes are photometric (lux), not the Johnson V band.** Schaefer's conversion is standard for naked-eye work. The colour term for white LED or halogen light against the V band is a few tenths of a magnitude, which is already stated as a limitation (note 4).
