"""
One-off helper that inserted the photographs and figures into the website pages
(kept for the record, and for re-use if the pages are rebuilt).

Image sources and licences: docs/img/CREDITS.md. Metadata: data/inputs/image_credits.json.
Run from the repository root:  python analysis/add_images.py
"""
import json
import os

from PIL import Image

M = json.load(open("data/inputs/image_credits.json"))
OWN = ('Figure: this project. <a href="https://github.com/zacharyslate/marfa-lights-investigation/tree/main/publication">'
       'Code, data and full-size PDF</a>.')


def credit(k):
    m = M[k]
    pg = m["page"]
    if m["artist"] == "Carol M. Highsmith":
        return f'Photo: Carol M. Highsmith, Library of Congress. <a href="{pg}">Public domain</a>.'
    if k == "nps_chisos_night":
        return f'Photo: National Park Service, Big Bend National Park. <a href="{pg}">Public domain</a>.'
    if k == "shafter_section":
        return f'Figure: C. P. Ross, U.S. Geological Survey Bulletin 928-B (1943). <a href="{pg}">Public domain</a>.'
    if k == "lights_hanson":
        return (f'Photo: Jon Hanson, 9 May 2009, via <a href="{pg}">Wikimedia Commons</a>, '
                f'<a href="https://creativecommons.org/licenses/by/2.0/">CC BY 2.0</a>, cropped.')
    if k == "viewing_area":
        return (f'Photo: Allison Meier, 2021, via <a href="{pg}">Wikimedia Commons</a>, '
                f'<a href="https://creativecommons.org/licenses/by/2.0/">CC BY 2.0</a>.')
    raise KeyError(k)


def img(k, alt, cls="photo", cap="", sizes="(max-width: 900px) 100vw, 800px", eager=False):
    if k.startswith("fig"):
        W, H = Image.open(f"docs/img/{k}-1600.webp").size
        src = f"img/{k}-900.webp"
        srcset = f"img/{k}-900.webp 900w, img/{k}-1600.webp 1600w"
        cr = OWN
    else:
        files = sorted([f for f in os.listdir("docs/img") if f.startswith(k + "-")],
                       key=lambda f: int(f.split("-")[-1][:-5]))
        W, H = Image.open("docs/img/" + files[-1]).size
        src = "img/" + files[0]
        srcset = ", ".join(f'img/{f} {f.split("-")[-1][:-5]}w' for f in files)
        cr = credit(k)
    cap = f"<b>{cap}</b> " if cap else ""
    return (f'<figure class="{cls}"><img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{W}" height="{H}" '
            f'alt="{alt}" loading="{"eager" if eager else "lazy"}" decoding="async"><figcaption>{cap}{cr}</figcaption></figure>')


def edit(p, pairs):
    s = open(p).read()
    for a, b in pairs:
        assert s.count(a) == 1, (p, a[:80])
        s = s.replace(a, b)
    open(p, "w").write(s)


LH = "Visitors on the Viewing Area platform at night, lit by low red lights, looking out over the dark flat"
VA = "The round adobe-style Marfa Lights Viewing Area building and stone wall under a blue sky"


def main():
    edit("docs/index.html", [
        ('  <section class="hero">',
         "  " + img("nps_chisos_night", "The Milky Way arching over the dark silhouette of the Chisos Mountains in Big Bend National Park",
                    "hero-photo", sizes="100vw", eager=True) + '\n  <section class="hero">'),
        ('  <section class="cards" aria-label="Sections">',
         '  <div class="photos2">\n    '
         + img("lights_hanson", LH, "photo wide", "Watching from the platform.", sizes="(max-width: 700px) 100vw, 600px") + "\n    "
         + img("viewing_area", VA, "photo wide", "The Viewing Area on US-90 by day.", sizes="(max-width: 700px) 100vw, 600px")
         + '\n  </div>\n\n  <section class="cards" aria-label="Sections">')])
    edit("docs/history.html", [
        ('  <div class="two">',
         "  " + img("courthouse", "The pink Presidio County Courthouse in Marfa with its silver dome under a blue sky", "photo banner",
                    "The Presidio County Courthouse in Marfa.", sizes="100vw") + '\n\n  <div class="two">'),
        ("      <h2>Why this matters for observing</h2>",
         "      " + img("lights_lamps", "A former grocery store in Marfa with a sign reading Marfa Lights and Lamps", "photo",
                        "The lights are part of the town's identity: a shop sign in Marfa.")
         + "\n\n      <h2>Why this matters for observing</h2>")])
    edit("docs/place.html", [
        ('  <section class="stats" aria-label="The setting in numbers">',
         "  " + img("sunset_brewster", "Dark mountain silhouettes under an orange and blue sunset sky in Brewster County", "photo banner",
                    "Dusk over the mountains south of Alpine. After dark, the skyline is your main guide to a light's height.",
                    sizes="100vw") + '\n\n  <section class="stats" aria-label="The setting in numbers">'),
        ("      <h2>Climate</h2>",
         "      " + img("shafter_section", "Geological cross-section through the Presidio silver mine at Shafter, showing faulted Permian limestone",
                        "photo plain", "Cross-section through the Presidio silver mine at Shafter.") + "\n      "
         + img("shafter", "Weathered old buildings and trees in the small community of Shafter", "photo",
               "Shafter today, 65 km from the platform at 219° true, at the far end of the US-67 stretch studied here.")
         + "\n\n      <h2>Climate</h2>"),
        ("      <h2>Dark skies</h2>",
         "      " + img("pricklypear", "Prickly-pear cactus and a fence of dry ocotillo stems in a Marfa yard", "photo",
                        "Chihuahuan Desert plants in Marfa.") + "\n\n      <h2>Dark skies</h2>")])
    edit("docs/science.html", [
        ("      <h2>The field studies</h2>",
         "      " + img("lights_hanson", LH, "photo wide", "Observers at the Viewing Area, 2009.") + "\n\n      <h2>The field studies</h2>"),
        ("      <h2>The Zone of Skepticism</h2>",
         "      " + img("fig02_panorama_zos", "Panorama from the Viewing Area showing the skyline, the visible stretches of US-67 and RM 2810, "
                        "towers, the railroad and the shaded Zone of Skepticism", "photo plain",
                        "The view from the platform, with every known light source and the Zone of Skepticism.")
         + "\n\n      <h2>The Zone of Skepticism</h2>"),
        ("      <h2>What would settle it</h2>",
         "      " + img("fig06_weighted_zone", "Panorama shaded by the expected number of ordinary lights per hour; most of the view below "
                        "the skyline is unshaded", "photo plain",
                        "How many ordinary lights pass each part of the view per hour on a typical night.") + "\n      "
         + img("fig03_headlights", "Headlamp beam patterns and the predicted brightness of cars on US-67 and RM 2810 facing the Viewing Area",
               "photo plain", "Direction decides brightness: measured headlamp beams, and how bright a car facing the platform would look.")
         + "\n\n      <h2>What would settle it</h2>")])
    edit("docs/visit.html", [
        ('  <div class="two">',
         "  " + img("viewing_area", VA, "photo banner", "The Marfa Lights Viewing Area, about nine miles east of Marfa on US-90.",
                    sizes="100vw") + '\n\n  <div class="two">'),
        ("      <h2>Dark-sky manners</h2>",
         "      " + img("lights_hanson", LH, "photo wide", "Low red lighting at the platform keeps everyone's eyes dark-adapted.")
         + "\n\n      <h2>Dark-sky manners</h2>")])
    s = open("docs/community.html").read()
    for title, k, alt in [
            ("Greater Big Bend International Dark Sky Reserve", "sunset_brewster", "Mountain silhouettes at dusk in Brewster County, inside the dark-sky reserve"),
            ("McDonald Observatory", "mcdonald", "White telescope domes of McDonald Observatory on a mountaintop in the Davis Mountains"),
            ("Big Bend National Park", "nps_chisos_night", "The Milky Way over the Chisos Mountains in Big Bend National Park"),
            ("Big Bend Ranch State Park and the Chinati Mountains", "bbr", "Rugged desert hills and a green valley in Big Bend Ranch State Park")]:
        a = f"<h3>{title}</h3>"
        assert s.count(a) == 1, a
        s = s.replace(a, img(k, alt, "photo wide", "", sizes="(max-width: 900px) 100vw, 560px") + "\n        " + a)
    for a, b in [('  <div class="two">', img("courthouse", "The pink Presidio County Courthouse in Marfa with its silver dome", "photo banner",
                                               "Marfa's courthouse square hosts the Marfa Lights Festival each Labor Day weekend.", sizes="100vw")),
                 ('  <section class="cta">', img("lights_hanson", LH, "photo banner", "Everyone at the platform shares the same night.", sizes="100vw"))]:
        assert s.count(a) == 1, a
        s = s.replace(a, "  " + b + "\n\n" + a)
    open("docs/community.html", "w").write(s)
    edit("docs/report.html", [
        ('  <div class="two">',
         "  " + img("nps_chisos_night", "The Milky Way over a dark mountain skyline", "photo banner",
                    "A dark sky is a shared instrument. Careful records keep it useful.", sizes="100vw") + '\n\n  <div class="two">')])
    edit("docs/map.html", [
        ('      <svg id="pano" viewBox="0 0 640 260"',
         "      " + img("viewing_area", VA, "photo wide", "The platform you are standing on.", sizes="400px")
         + '\n      <svg id="pano" viewBox="0 0 640 260"')])
    print("ok")


if __name__ == "__main__":
    main()
