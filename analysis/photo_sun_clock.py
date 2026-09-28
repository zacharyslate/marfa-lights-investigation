"""Check the camera clock with the sunset frame (p03): register its skyline, measure the sun,
and find the time at which the Sun stood there as seen from the Viewing Area."""
import sys, json, math, datetime as dt
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, "analysis")
import photo_register as P
import astronomy as A

im = np.asarray(Image.open(f"{P.RAW}/p03.jpg").convert("RGB")).astype(float)
L = ndimage.uniform_filter(im.mean(2), size=(9, 9)); H, W = L.shape
sat = im.mean(2) > 250; lab, n = ndimage.label(sat)
k = np.argmax(ndimage.sum(sat, lab, range(1, n + 1))) + 1
scy, scx = ndimage.center_of_mass(sat, lab, k)
xs = np.arange(8, W - 8, 8); ys = []
for x in xs:
    col = L[1800:2500, x]; g = np.diff(col)
    ys.append(1800 + int(np.argmin(g)) if abs(x - scx) > 450 else np.nan)
ys = np.array(ys, float)
p, coarse, rms, mad = P.fit_pointing(xs, ys)
saz, sel = P.px_to_angles(np.array([scx]), np.array([scy]), p)
print("pointing", np.round(p, 4), "rms %.4f" % rms, "sun centre az %.3f el %.3f" % (saz[0], sel[0]))
obs = A.Observer(30.2751108, -103.8827973, 1495)
cam = dt.datetime(2018, 11, 21, 18, 49, 40)
best = None
for off_min in np.arange(-180, 180, 0.25):                   # camera clock minus true UTC-6 (CST) time
    t_cst = cam - dt.timedelta(minutes=float(off_min))
    t = A.Time.Make(t_cst.year, t_cst.month, t_cst.day, t_cst.hour + 6, t_cst.minute, t_cst.second)   # CST = UTC-6
    eq = A.Equator(A.Body.Sun, t, obs, True, True); hz = A.Horizon(t, obs, eq.ra, eq.dec, A.Refraction.Normal)
    d = math.hypot((hz.azimuth - saz[0]) * math.cos(math.radians(hz.altitude)), hz.altitude - sel[0])
    if best is None or d < best[0]: best = (d, off_min, hz.azimuth, hz.altitude, t_cst)
print("best match: camera clock is %+.1f min ahead of CST; sun then at az %.3f alt %.3f; mismatch %.3f deg; true time %s CST"
      % (best[1], best[2], best[3], best[0], best[4].strftime("%H:%M:%S")))
json.dump({"pointing": [float(v) for v in p], "skyline_rms_deg": rms, "sun_px": [scx, scy], "sun_az": float(saz[0]), "sun_el": float(sel[0]),
           "clock_offset_min_vs_CST": float(best[1]), "mismatch_deg": float(best[0])}, open(f"{P.OUT}/sun_clock.json", "w"), indent=1)
