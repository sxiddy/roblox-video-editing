"""Stage A: start a job folder with the four pages every job needs.

    python pipeline/new_job.py <job-name>

Creates jobs/<job-name>/ with BRIEF.md, STYLE.md, REFERENCE.md, EDIT.md, edit.json (from pipeline/templates)
and the folders the other scripts write into. Never overwrites an existing page.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

from config import JOBS

TEMPLATES = Path(__file__).resolve().parent / "templates"
FOLDERS = ["clips", "brand", "refs", "footage", "style", "music", "thumb", "renders", "deliver"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", help="short name: letters, digits, dash, underscore (e.g. tides-trailer-v2)")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,60}", a.job):
        sys.exit("STOP: job name may only use letters, digits, - and _")
    job = JOBS / a.job
    for f in FOLDERS:
        (job / f).mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    for t in sorted(p for p in TEMPLATES.iterdir() if p.suffix in (".md", ".json")):
        dst = job / t.name
        if dst.exists():
            print("kept   ", dst)
            continue
        dst.write_text(t.read_text(encoding="utf-8").replace("{job}", a.job).replace("{date}", today),
                       encoding="utf-8")
        print("created", dst)
    print(f"\nJob folder: {job}")
    print("Put the client's clips in clips/, logo and brand files in brand/, reference videos in refs/.")
    print("Next: fill BRIEF.md (Stage A) and get the user's confirmation before anything else.")

if __name__ == "__main__":
    main()
