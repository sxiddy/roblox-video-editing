"""Build the SFX library from Openverse (CC0 only) into Projects/media-library/sfx/<category>/.

    python pipeline/sfx_fetch.py [--per 8]

Writes sfx.json (title, creator, licence, source page) next to the files. CC0 needs no credit.
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request

from config import SFX

QUERIES = {
    "whoosh": ["whoosh", "swoosh"], "impact": ["cinematic impact", "boom hit"],
    "riser": ["riser", "reverse cymbal"], "sub_drop": ["sub drop", "bass drop"],
    "ui": ["ui click", "notification pop"], "water": ["water splash", "underwater"],
    "fire": ["fire crackle"], "wind": ["wind"], "footsteps": ["footsteps grass", "footsteps stone"],
    "ambience": ["forest ambience", "ocean waves", "rain", "cave ambience"],
    "glitch": ["glitch"], "sword": ["sword swing", "sword hit"],
}
LONG = {"ambience", "wind", "fire"}

def get(url, raw=False):
    r = urllib.request.Request(url, headers={"User-Agent": "sfx-library-builder/1.0"})
    d = urllib.request.urlopen(r, timeout=60).read()
    return d if raw else json.loads(d)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=8)
    a = ap.parse_args()
    index_path = SFX / "sfx.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    have = {i["id"] for i in index}
    for cat, qs in QUERIES.items():
        d = SFX / cat
        d.mkdir(parents=True, exist_ok=True)
        n = 0
        for q in qs:
            try:
                res = get("https://api.openverse.org/v1/audio/?" + urllib.parse.urlencode(
                    {"q": q, "license": "cc0", "page_size": 20}))["results"]
            except Exception as e:
                print("FAIL query", q, repr(e)[:80])
                continue
            for r in res:
                if n >= a.per:
                    break
                dur = (r.get("duration") or 0) / 1000
                lim = 180 if cat in LONG else 20
                if r["id"] in have or not (0.2 <= dur <= lim) or (r.get("filetype") or "mp3") not in ("mp3", "wav", "ogg", "flac"):
                    continue
                name = re.sub(r"[^a-z0-9]+", "-", (r.get("title") or "sfx").lower()).strip("-")[:40]
                f = d / f"{name}-{r['id'][:6]}.{r.get('filetype') or 'mp3'}"
                try:
                    f.write_bytes(get(r["url"], raw=True))
                except Exception:
                    continue
                index.append({"id": r["id"], "file": str(f), "category": cat, "title": r.get("title"),
                              "creator": r.get("creator"), "licence": "CC0", "duration": dur,
                              "source": r.get("foreign_landing_url")})
                have.add(r["id"])
                n += 1
            time.sleep(3)
        print(f"{cat}: {n} new")
        index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print("total", len(index), "->", index_path)

if __name__ == "__main__":
    main()
