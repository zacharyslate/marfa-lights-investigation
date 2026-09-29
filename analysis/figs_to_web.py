"""Convert the publication figures (publication/figures/fig*.png) into the web images used by docs/science.html
(900 and 1600 px wide WebP) and update the width/height attributes of those <img> tags.
Run from the repository root after analysis/pub_figures.py and analysis/photo_figures.py."""
import glob, os, re
from PIL import Image

page = "docs/science.html"
html = open(page, encoding="utf-8").read()
for p in sorted(glob.glob("publication/figures/fig*.png")):
    if "fig00_" in p:            # manuscript-only schematic, not on the website
        continue
    name = os.path.basename(p)[:-4]
    im = Image.open(p).convert("RGB")
    for w in (900, 1600):
        h = round(im.height * w / im.width)
        im.resize((w, h), Image.LANCZOS).save(f"docs/img/{name}-{w}.webp", "WEBP", quality=88, method=6)
    h16 = round(im.height * 1600 / im.width)
    html = re.sub(rf'(src="img/{name}-900\.webp"[^>]*?width=")\d+(" height=")\d+(")', rf"\g<1>1600\g<2>{h16}\g<3>", html)
    print(name, im.size, "->", 1600, h16)
open(page, "w", encoding="utf-8").write(html)
