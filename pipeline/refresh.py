#!/usr/bin/env python3
"""Weekly refresh: re-fetch the saved collection, rebuild the index,
enrich thin posts via comments, and regenerate the Recipe Finder page."""
import os, shutil, subprocess, sys

HOME = os.path.expanduser("~")
RF = os.path.join(HOME, "workspace/recipe-finder")
PAGES = os.path.join(HOME, "workspace/instagram/food-recipes/pages")

def run(cmd):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    sys.stdout.write(r.stdout[-2000:])
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"FAILED: {cmd[1]}")

# clean slate so unsaved posts don't linger
shutil.rmtree(PAGES, ignore_errors=True)

run([sys.executable, os.path.join(HOME, "workspace/instagram/food-recipes/fetch_saved.py")])
run([sys.executable, os.path.join(RF, "build_index.py")])
run([sys.executable, os.path.join(RF, "enrich_comments.py")])
run([sys.executable, os.path.join(RF, "fetch_thumbs.py")])
run([sys.executable, os.path.join(RF, "inject.py")])
print("REFRESH DONE", flush=True)
