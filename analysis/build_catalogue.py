"""Build docs/data/catalogue.json for the sightings catalogue page (docs/sightings.html).

    python analysis/build_catalogue.py

Inputs
  data/inputs/sightings_research.json         documented sightings and observing campaigns, each with its sources
                                              (compiled 2 Oct 2026; every source was opened or found in a search;
                                              'opened' says which, and 'source_status' says how direct it is)
  data/inputs/published_photos_research.json  published photographs claimed to show the lights, with provenance
  data/derived/photos_hist/reanalysis.json    our re-analysis of the photos we could download (photo checker)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))  # noqa: E731

# conflicts and unsupported claims found while compiling the catalogue (each traceable to the sources in the entries)
NOTES = [
    "The 1883 Robert Ellison sighting, called the 'first recorded sighting' on the 1988 historical marker, rests on family tradition: his 1937 memoir does not mention the lights (Texas Monthly, 2006).",
    "The earliest printed account is uncertain: a San Angelo Times piece of February 1945 (Texas Monthly, 2006) or Paul Moran's Coronet article of July 1957 (Skeptoid; Wikipedia).",
    "The Handbook of Texas places the WWII pilot searches at 'Midland Army Air Field'; the nearby field was Marfa Army Air Field.",
    "The UT Dallas Society of Physics Students study is dated May 2004 by Wikipedia and Texas Monthly, and 11–13 May 2005 by Slashdot (December 2005). The report itself could not be opened.",
    "Media often credit the 2011 Journal of Atmospheric and Solar-Terrestrial Physics paper with the headlight finding; that finding is in the 2009 American Journal of Physics paper. The 2011 paper describes one very bright, unexplained light seen from automated stations.",
    "James Bunnell's May 2003 photographs are dated 7 May in the FOTOCAT re-analysis (Ballester Olmos and Borraz, 2020) and 8 May in Bunnell (2021). FOTOCAT also finds his compass bearings off by roughly 2–4°.",
]


def main():
    sights = J("data/inputs/sightings_research.json")
    photos = J("data/inputs/published_photos_research.json")
    rean = {r["id"]: r for r in J("data/derived/photos_hist/reanalysis.json")["photos"]}
    S = []
    for e in sights:
        S.append({
            "id": e["id"], "date": e.get("date"), "time": e.get("time"), "who": e.get("observers"), "where": e.get("observer_location"),
            "bearing": e.get("bearing"), "what": e.get("description"), "cond": e.get("conditions"), "expl": e.get("explanation_offered"),
            "src": [{"c": s.get("cite"), "u": s.get("url"), "o": bool(s.get("opened"))} for s in e.get("sources", [])],
            "status": e.get("source_status"), "type": e.get("evidence_type"),
            "test": (e.get("los_comparable") or {}).get("rating"), "testwhy": (e.get("los_comparable") or {}).get("reason"),
        })
    P = []
    for p in photos:
        r = rean.get(p["id"])
        P.append({
            "id": p["id"], "title": p.get("title"), "by": p.get("author"), "pub": p.get("publisher"), "taken": p.get("date_taken"), "time": p.get("time"),
            "url": p.get("page_url"), "from": p.get("taken_from"), "dir": p.get("direction"), "cam": p.get("camera"), "lic": p.get("licence"),
            "claim": p.get("claim"), "anal": p.get("analysability"), "notes": p.get("notes"),
            "re": None if not r else {"verdict": r["verdict"], "result": r["result"], "method": r.get("method"),
                                      "az": (r.get("light") or {}).get("az_true_deg"), "el": (r.get("light") or {}).get("el_deg"),
                                      "sigma": (r.get("alignment") or {}).get("sigma_deg")},
        })
    out = {"compiled": "2026-10-02", "sightings": S, "photos": P, "notes": NOTES,
           "counts": {"sightings": len(S), "testable": sum(1 for s in S if s["test"] == "yes"), "partly": sum(1 for s in S if s["test"] == "partly"),
                      "photos": len(P), "reanalysed": len(rean), "explained": sum(1 for r in rean.values() if r["verdict"].startswith("explained"))}}
    open(os.path.join(ROOT, "docs/data/catalogue.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(out["counts"])


if __name__ == "__main__":
    main()
