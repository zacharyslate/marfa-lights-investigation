"""Usage (from the repository root, ZACH-venv):
    python analysis/video/video_track.py VIDEO.mp4 track.json
    python analysis/video/video_render.py VIDEO.mp4 track.json OUTDIR
"""
"""Render (1) the original video with the model drawn on every frame and (2) a side-by-side: stabilised video with the
model, bearing-versus-time tracks, and a map of US-67 with the implied car positions."""
import os, sys, json, math, subprocess, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), cv2
sys.path.insert(0, ROOT + "/analysis")
from photo_overlay import S, m2d
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
VID, TRK, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS = 1920, 1080, 30
T = json.load(open(TRK)); N = len(T)
FD = "/usr/share/fonts/truetype/dejavu/"
F = lambda s, b=False: ImageFont.truetype(FD + ("DejaVuSans-Bold.ttf" if b else "DejaVuSans.ttf"), s)
FM = lambda s: ImageFont.truetype(FD + "DejaVuSansMono.ttf", s)
BG = (11, 14, 19); INK = (233, 231, 225); INK2 = (188, 194, 202); MUT = (139, 148, 158); RULE = (40, 49, 61)
ROAD = (255, 154, 42); HID = (120, 128, 138); SKY = (130, 210, 255)
COL = {"A": (109, 179, 255), "B": (199, 146, 234), "C": (95, 211, 141), "D": (255, 90, 79)}
WIN = {"A": (230.3, 231.2), "B": (233.4, 234.2), "C": (236.3, 237.3), "D": (229.1, 229.6)}
SK = np.array([(r[0], m2d(r[1])) for r in S["sky"]])
HWA = sorted(S["hwy"], key=lambda h: h[8])                    # all US-67 samples by chainage
HWV = [h for h in HWA if h[6] != "h"]
TOWER = [t for t in S["towers"] if t["id"] == "1053636"][0]
# ---------------------------------------------------------------- camera geometry
def basis(az0, el0, roll):
    a, e, r = map(math.radians, (az0, el0, roll))
    Fv = np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])
    R0 = np.array([math.cos(a), -math.sin(a), 0.0]); U0 = np.cross(R0, Fv)
    R = math.cos(r) * R0 + math.sin(r) * U0; U = -math.sin(r) * R0 + math.cos(r) * U0
    return np.stack([R, U, Fv], 1)                              # columns R, U, F
def dirs(az, el):
    az, el = np.radians(np.asarray(az, float)), np.radians(np.asarray(el, float))
    return np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], -1)
def proj(cam, az, el, w, h):
    C = basis(*cam[:3]); f = cam[3]; c = dirs(az, el) @ C
    return w / 2 + f * c[..., 0] / c[..., 2], h / 2 - f * c[..., 1] / c[..., 2], c[..., 2]
def homog(cam_i, cam_v, wv, hv):
    Ci, Cv = basis(*cam_i[:3]), basis(*cam_v[:3]); fi, fv = cam_i[3], cam_v[3]
    A = np.array([[1 / fi, 0, -W / 2 / fi], [0, -1 / fi, H / 2 / fi], [0, 0, 1]])
    B = np.array([[fv, 0, wv / 2], [0, -fv, hv / 2], [0, 0, 1]])
    return B @ Cv.T @ Ci @ A
# smooth lens and roll (they change slowly); keep bearing and tilt per frame
cams = np.array([t["cam"] for t in T])
from scipy.ndimage import median_filter, uniform_filter1d
cams[:, 2] = uniform_filter1d(median_filter(cams[:, 2], 9), 9); cams[:, 3] = uniform_filter1d(median_filter(cams[:, 3], 15), 15)
# ---------------------------------------------------------------- tracks
tracks = {}
for k, (lo, hi) in WIN.items():
    det = {}
    for t in T:
        for s in t["spots"]:
            if lo <= s["az"] <= hi: det[t["i"]] = s
    ii = np.array(sorted(det)); tt = ii / FPS; az = np.array([det[i]["az"] for i in ii]); el = np.array([det[i]["el"] for i in ii])
    sl, ic = np.polyfit(tt, az, 1)
    tracks[k] = dict(det=det, sl=sl, ic=ic, sep=float(np.median([det[i]["hwy_sep"] for i in ii])), el=float(np.median(el)),
                     below=float(np.median([det[i]["below_sky_deg"] for i in ii])), n=len(ii),
                     rgb=np.mean([[det[i][c] for c in "rgb"] for i in ii], 0))
def chain_of_az(a, near_ch):
    """Chainage on US-67 (km) where the modelled bearing equals a, searched within 2 km of near_ch."""
    seg = [h for h in HWA if abs(h[8] - near_ch) < 2.0]
    for h0, h1 in zip(seg, seg[1:]):
        if (h0[2] - a) * (h1[2] - a) <= 0 and h1[2] != h0[2]:
            return h0[8] + (a - h0[2]) / (h1[2] - h0[2]) * (h1[8] - h0[8])
    return min(seg, key=lambda h: abs(h[2] - a))[8]
def at_chain(c, idx):
    ch = np.array([h[8] for h in HWA]); return float(np.interp(c, ch, [h[idx] for h in HWA]))
for k in "ABC":
    tr = tracks[k]; a0 = tr["ic"]; a1 = tr["ic"] + tr["sl"] * (N - 1) / FPS
    near = min(HWV, key=lambda h: abs(h[2] - a0))[8]
    c0 = chain_of_az(a0, near); c1 = chain_of_az(a1, near)
    tr["c0"], tr["c1"] = c0, c1; tr["kmh"] = abs(c1 - c0) / ((N - 1) / FPS) * 3600
    tr["d0"], tr["d1"] = at_chain(c0, 3), at_chain(c1, 3)
    tr["dir"] = "toward the platform (northbound)" if tr["d1"] < tr["d0"] else "away from the platform"
# tower beacon: on/off rhythm
pres = np.array([1.0 if i in tracks["D"]["det"] else 0.0 for i in range(N)])
x = pres - pres.mean(); ac = np.correlate(x, x, "full")[N - 1:]; ac /= ac[0]
lag = int(np.argmax(ac[20:120]) + 20); tracks["D"]["period"] = lag / FPS; tracks["D"]["duty"] = float(pres.mean())
D = tracks["D"]; D["sep_tower_az"] = TOWER["az"] - D["ic"]; D["tower_el"] = m2d(TOWER["a"])
summary = {k: {kk: (float(v) if isinstance(v, (float, np.floating)) else v) for kk, v in tr.items() if kk not in ("det", "rgb")} for k, tr in tracks.items()}
for k in summary: summary[k]["rgb"] = [round(float(v)) for v in tracks[k]["rgb"]]
json.dump(summary, open(OUTDIR + "/summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
# ---------------------------------------------------------------- map (UTM 13N, from the 20 m terrain mosaic)
tf = Transformer.from_crs("EPSG:4326", "EPSG:26913", always_xy=True)
VIEW = S["viewer"]; PX, PY = tf.transform(VIEW["lon"], VIEW["lat"]) if isinstance(VIEW, dict) else tf.transform(-103.8827973, 30.2751108)
MX0, MX1, MY0, MY1 = PX - 33000, PX + 3000, PY - 28000, PY + 3500
MW, MH = 720, 630
z = np.load(ROOT + "/data/dem/terrain20.npz")["z"]; X0, Y1g, RES = 540000, 3364000, 20
c0, c1 = int((MX0 - X0) / RES), int((MX1 - X0) / RES); r0, r1 = int((Y1g - MY1) / RES), int((Y1g - MY0) / RES)
zz = np.nan_to_num(z[r0:r1, c0:c1], nan=np.nanmean(z[r0:r1, c0:c1]))
gy, gx = np.gradient(zz * 3, RES); az_s, alt_s = math.radians(315), math.radians(40)
slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
hs = np.sin(alt_s) * np.cos(slope) + np.cos(alt_s) * np.sin(slope) * np.cos(az_s - aspect)
hs = (hs - hs.min()) / (hs.max() - hs.min())
base = (np.stack([hs * 60 + 22, hs * 62 + 26, hs * 66 + 32], -1)).clip(0, 255).astype(np.uint8)
MAPBG = Image.fromarray(base).resize((MW, MH), Image.LANCZOS)
def mp(lon, lat):
    x, y = tf.transform(lon, lat); return ((x - MX0) / (MX1 - MX0) * MW, (MY1 - y) / (MY1 - MY0) * MH)
g = ImageDraw.Draw(MAPBG, "RGBA")
for rd in S["roads"]:
    pts = [mp(q[1], q[0]) for q in rd["p"]]
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 40: g.line([a, b], fill=(150, 156, 166, 110), width=1)
pts = [mp(h[1], h[0]) for h in HWA]
g.line(pts, fill=(170, 176, 186, 200), width=2)
for h0, h1 in zip(HWA, HWA[1:]):
    if h0[6] != "h" and h1[6] != "h": g.line([mp(h0[1], h0[0]), mp(h1[1], h1[0])], fill=ROAD + (255,), width=5)
ppx = mp(-103.8827973, 30.2751108)
for tw in [TOWER]:
    q = mp(tw["lon"], tw["lat"]); g.ellipse([q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6], outline=(255, 90, 79, 255), width=2)
for tn in S["towns"]:
    q = mp(tn["lon"], tn["lat"])
    if 0 < q[0] < MW and 0 < q[1] < MH: g.text((q[0] + 6, q[1] - 8), tn["n"], font=F(15, True), fill=INK2)
g.text((12, MH - 26), "N ↑   10 km", font=F(14), fill=INK2); sc = 10000 / (MX1 - MX0) * MW
g.line([(68, MH - 12), (68 + sc, MH - 12)], fill=INK2, width=2)
# legend on the map
g.rectangle([MW - 250, MH - 74, MW - 8, MH - 8], fill=(11, 14, 19, 200))
g.line([(MW - 238, MH - 58), (MW - 208, MH - 58)], fill=ROAD, width=5); g.text((MW - 200, MH - 66), "US-67 in view (model)", font=F(13), fill=INK2)
g.line([(MW - 238, MH - 36), (MW - 208, MH - 36)], fill=(170, 176, 186), width=2); g.text((MW - 200, MH - 44), "US-67 hidden by terrain", font=F(13), fill=INK2)
def car_lonlat(k, t):
    tr = tracks[k]; c = tr["c0"] + (tr["c1"] - tr["c0"]) * t / ((N - 1) / FPS)
    return at_chain(c, 1), at_chain(c, 0)
# beacon: where the light is if it is at the tower's registered distance
def dest(lat, lon, az, km):
    from pyproj import Geod
    lo, la, _ = Geod(ellps="WGS84").fwd(lon, lat, az, km * 1000); return la, lo
D["implied_latlon"] = dest(30.2751108, -103.8827973, D["ic"], TOWER["d"])
# ---------------------------------------------------------------- the stabilised view
VW, VH = 1170, 560
VC = np.array([233.1, 0.05, 0.0, 7400.0])
def vproj(az, el):
    x, y, zf = proj(VC, az, el, VW, VH); return x, y
MODEL = Image.new("RGBA", (VW, VH), (0, 0, 0, 0)); gm = ImageDraw.Draw(MODEL)
xs, ys = vproj(SK[:, 0], SK[:, 1]); ok = (xs > -50) & (xs < VW + 50)
gm.line(list(zip(xs[ok], ys[ok])), fill=SKY + (200,), width=2)
for h in HWA:
    x, y = vproj(h[2], m2d(h[7]))
    if 0 < x < VW:
        if h[6] == "h": gm.ellipse([x - 1.2, y - 1.2, x + 1.2, y + 1.2], fill=HID + (150,))
        else: gm.ellipse([x - 2.2, y - 2.2, x + 2.2, y + 2.2], fill=ROAD + (220,))
tx, ty = vproj(TOWER["az"], m2d(TOWER["a"]))
gm.ellipse([tx - 10, ty - 10, tx + 10, ty + 10], outline=(255, 90, 79, 230), width=2)
gm.text((tx - 70, ty + 14), "registered tower", font=F(13), fill=(255, 140, 130, 255))
for a in range(229, 238):
    x, _ = vproj(a, 0)
    gm.line([(x, VH - 14), (x, VH - 6)], fill=INK2 + (200,), width=1); gm.text((x - 14, VH - 32), f"{a}°", font=F(13), fill=INK2 + (220,))
# ---------------------------------------------------------------- per-frame rendering
def frames():
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", VID, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    while True:
        b = pr.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
def enc(path, w, h):
    return subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
E1 = enc(OUTDIR + "/marfa_video_model_overlay.mp4", W, H)
E2 = enc(OUTDIR + "/marfa_video_side_by_side.mp4", 1920, 1080)
LBL = {"A": "car", "B": "car", "C": "car", "D": "red beacon"}
def label_text(k):
    tr = tracks[k]
    if k == "D": return "D  red, flashing"
    return f"{k}  US-67 · {tr['d0']:.0f} km"
# chart geometry (bearing vs time, one row per light)
CX0, CY0, CW, CHh = 70, 650, 1080, 400
ROWS = ["C", "B", "A", "D"]; RH = CHh / 4
def chart_base():
    im = Image.new("RGB", (1170, 420), BG); g = ImageDraw.Draw(im, "RGBA")
    g.text((0, 0), "Bearing of each light over time", font=F(18, True), fill=INK)
    g.text((330, 3), "dots: measured each frame · grey band: road hidden by terrain (model) · line: steady motion fit", font=F(13), fill=MUT)
    for r, k in enumerate(ROWS):
        y0 = 30 + r * 95; tr = tracks[k]; a_mid = tr["ic"] + tr["sl"] * 9.2; span = 0.20
        g.rectangle([60, y0, 1160, y0 + 82], outline=RULE)
        if k != "D":
            seg = [h for h in HWA if min(tr["c0"], tr["c1"]) - 1.5 <= h[8] <= max(tr["c0"], tr["c1"]) + 1.5]
            for j, h in enumerate(seg):
                if h[6] != "h" or j == 0 or j == len(seg) - 1: continue
                lo_a = (seg[j - 1][2] + h[2]) / 2; hi_a = (seg[j + 1][2] + h[2]) / 2
                ya = y0 + 82 - (lo_a - (a_mid - span)) / (2 * span) * 82; yb = y0 + 82 - (hi_a - (a_mid - span)) / (2 * span) * 82
                top, bot = max(y0 + 1, min(ya, yb)), min(y0 + 81, max(ya, yb))
                if bot - top < 4: top, bot = (top + bot) / 2 - 2, (top + bot) / 2 + 2
                top, bot = max(y0 + 1, top), min(y0 + 81, bot)
                if bot > top: g.rectangle([61, top, 1159, bot], fill=(150, 158, 170, 140))
        g.text((8, y0 + 30), k, font=F(22, True), fill=COL[k])
        g.text((64, y0 + 2), f"{a_mid - span + 0.02:.2f}°–{a_mid + span:.2f}°", font=F(11), fill=MUT)
        t0x = lambda t: 60 + t / ((N - 1) / FPS) * 1100
        g.line([(t0x(0), y0 + 82 - (tr["ic"] - (a_mid - span)) / (2 * span) * 82), (t0x((N - 1) / FPS), y0 + 82 - (tr["ic"] + tr["sl"] * (N - 1) / FPS - (a_mid - span)) / (2 * span) * 82)], fill=COL[k] + (110,), width=1)
        tr["row"] = (y0, a_mid, span)
    for s in range(0, 19, 2):
        x = 60 + s / ((N - 1) / FPS) * 1100; g.text((x - 6, 30 + 4 * 95 - 10), f"{s}s", font=F(11), fill=MUT)
    return im
CHART = chart_base()
cg = ImageDraw.Draw(CHART, "RGBA")
for fi, fr in enumerate(frames()):
    cam = cams[fi]; t = fi / FPS
    # (1) original frame with the model
    im1 = Image.fromarray(fr.copy()); g1 = ImageDraw.Draw(im1, "RGBA")
    x, y, zf = proj(cam, SK[:, 0], SK[:, 1], W, H); ok = (x > -100) & (x < W + 100) & (zf > 0)
    g1.line(list(zip(x[ok], y[ok])), fill=SKY + (190,), width=2)
    for h in HWA:
        x, y, zf = proj(cam, h[2], m2d(h[7]), W, H)
        if 0 < x < W:
            if h[6] == "h": g1.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=HID + (140,))
            else: g1.ellipse([x - 2.6, y - 2.6, x + 2.6, y + 2.6], fill=ROAD + (210,))
    x, y, _ = proj(cam, TOWER["az"], m2d(TOWER["a"]), W, H); g1.ellipse([x - 11, y - 11, x + 11, y + 11], outline=(255, 90, 79, 220), width=2)
    for k, tr in tracks.items():
        s = tr["det"].get(fi)
        if s:
            g1.ellipse([s["x"] - 16, s["y"] - 16, s["x"] + 16, s["y"] + 16], outline=COL[k] + (255,), width=2)
            g1.text((s["x"] - 30, s["y"] + 22), label_text(k), font=F(18, True), fill=COL[k])
    g1.rectangle([0, 0, W, 56], fill=(11, 14, 19, 190))
    g1.text((20, 14), "Model overlay: blue = modelled skyline · orange = where US-67 is in view · grey = US-67 hidden by terrain · red ring = registered lit tower", font=F(20), fill=INK)
    g1.text((W - 220, H - 40), f"t = {t:5.2f} s", font=FM(22), fill=INK)
    E1.stdin.write(np.asarray(im1).tobytes())
    # (2) side by side
    Hm = homog(cam, VC, VW, VH)
    st = cv2.warpPerspective(fr, Hm, (VW, VH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=BG)
    vimg = Image.fromarray(st).convert("RGBA"); vimg.alpha_composite(MODEL); gv = ImageDraw.Draw(vimg, "RGBA")
    for k, tr in tracks.items():
        s = tr["det"].get(fi)
        if s:
            x, y = vproj(s["az"], s["el"]); gv.ellipse([x - 14, y - 14, x + 14, y + 14], outline=COL[k] + (255,), width=2)
            gv.text((x - 6, y - 38), k, font=F(18, True), fill=COL[k])
            r = tr["row"]; xx = 60 + t / ((N - 1) / FPS) * 1100; yy = r[0] + 82 - (s["az"] - (r[1] - r[2])) / (2 * r[2]) * 82
            if r[0] < yy < r[0] + 82: cg.ellipse([xx - 1.6, yy - 1.6, xx + 1.6, yy + 1.6], fill=COL[k] + (230,))
    out = Image.new("RGB", (1920, 1080), BG); go = ImageDraw.Draw(out, "RGBA")
    go.text((24, 16), "A video of “Marfa lights” checked against the line-of-sight model", font=F(28, True), fill=INK)
    go.text((24, 52), "Every frame lined up on the modelled skyline (median residual 1.6 px, about 0.01°); the view below is stabilised to fixed bearings", font=F(16), fill=INK2)
    out.paste(vimg.convert("RGB"), (24, 84))
    go.rectangle([24, 84, 24 + VW, 84 + VH], outline=RULE)
    out.paste(CHART, (24, 656))
    xx = 24 + 60 + t / ((N - 1) / FPS) * 1100; go.line([(xx, 686), (xx, 656 + 30 + 4 * 95 - 14)], fill=(233, 231, 225, 120), width=1)
    # map
    mimg = MAPBG.copy().convert("RGBA"); gm2 = ImageDraw.Draw(mimg, "RGBA")
    for k in "ABC":
        lon, lat = car_lonlat(k, t); q = mp(lon, lat)
        lon0, lat0 = car_lonlat(k, 0); q0 = mp(lon0, lat0)
        seen = fi in tracks[k]["det"]
        gm2.line([ppx, q], fill=COL[k] + ((170,) if seen else (60,)), width=1)
        gm2.line([q0, q], fill=COL[k] + (255,), width=3)
        r = 6 if seen else 5
        gm2.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=(COL[k] + (255,)) if seen else (40, 44, 52, 255), outline=COL[k] + (255,), width=2)
        gm2.text((q[0] + 8, q[1] - 22), k, font=F(16, True), fill=COL[k])
    la, lo = D["implied_latlon"]; q = mp(lo, la); on = fi in D["det"]
    gm2.line([ppx, q], fill=COL["D"] + ((150,) if on else (50,)), width=1)
    gm2.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], fill=(COL["D"] + (255,)) if on else (60, 30, 30, 255))
    gm2.text((q[0] - 14, q[1] + 8), "D", font=F(16, True), fill=COL["D"])
    qt = mp(TOWER["lon"], TOWER["lat"]); gm2.text((qt[0] + 9, qt[1] - 8), "registered tower", font=F(12), fill=(255, 140, 130, 255))
    gm2.ellipse([ppx[0] - 7, ppx[1] - 7, ppx[0] + 7, ppx[1] + 7], fill=(240, 164, 58, 255), outline=(11, 14, 19, 255), width=2)
    gm2.text((ppx[0] - 120, ppx[1] + 8), "Viewing Area", font=F(15, True), fill=(240, 164, 58))
    out.paste(mimg.convert("RGB"), (1176, 84)); go.rectangle([1176, 84, 1176 + MW, 84 + MH], outline=RULE)
    go.text((1186, 92), "Where each light is, if it is what the model says", font=F(16, True), fill=INK)
    # cards
    y = 728
    for k in "ABCD":
        tr = tracks[k]; seen = fi in tr["det"]
        go.text((1180, y), k, font=F(22, True), fill=COL[k])
        if k == "D":
            l1 = f"red, flashing every {tr['period']:.1f} s, not moving"
            l2 = f"{tr['ic']:.2f}° true · {abs(tr['sep_tower_az']):.1f}° left of the registered tower"
            l3 = "verdict: almost certainly a tower beacon (position to confirm)"
        else:
            pa = tr["ic"] + tr["sl"] * t; half = math.degrees(math.atan(W / 2 / cam[3]))
            if seen: why = "in view"
            elif abs(pa - cam[0]) > half - 0.05: why = "outside the camera's view"
            else:
                seg = [h for h in HWA if min(tr["c0"], tr["c1"]) - 1.0 <= h[8] <= max(tr["c0"], tr["c1"]) + 1.0]
                why = "hidden by terrain here (model)" if min(seg, key=lambda h: abs(h[2] - pa))[6] == "h" else "not detected"
            l1 = f"white, moving {tr['sl'] * 60:+.2f}°/min · {why}"
            l2 = f"on US-67 to {tr['sep']:.2f}° · {tr['d0']:.1f} km · ~{tr['kmh']:.0f} km/h toward Marfa"
            l3 = "verdict: a car's headlights on US-67"
        go.text((1210, y + 1), l1, font=F(15), fill=INK); go.text((1210, y + 21), l2, font=F(14), fill=INK2); go.text((1210, y + 40), l3, font=F(14, True), fill=COL[k])
        y += 72
    go.text((1180, 1026), "Model: zacharyslate.github.io/marfa-lights-investigation", font=F(13), fill=MUT); go.text((1180, 1046), "USGS 1 m lidar, normal refraction (k = 0.13) · video: posted on Reddit, author unknown", font=F(13), fill=MUT)
    E2.stdin.write(np.asarray(out).tobytes())
    if fi in (0, 100, 200, 352, 552):
        out.save(OUTDIR + f"/sbs_{fi:03d}.jpg", quality=88); im1.save(OUTDIR + f"/ovl_{fi:03d}.jpg", quality=85)
for E in (E1, E2):
    E.stdin.close(); E.wait()
print("done")
