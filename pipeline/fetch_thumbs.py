#!/usr/bin/env python3
"""Fetch og:image thumbnails for recipes, in polite resumable batches.

- Reads data/index.json for recipe links.
- Stores {id: {url, fetched_at}} in data/thumbs.json, saving progress as it goes.
- Skips ids with a fresh thumb (< 21 days old); refetches stale ones.
- Rerunning resumes where it left off.
"""
import json, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
DATA = os.path.join(HOME, "workspace/recipe-finder/data")
IDX = os.path.join(DATA, "index.json")
THUMBS = os.path.join(DATA, "thumbs.json")
STALE_DAYS = 21
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def fetch_thumb(url):
    try:
        p = subprocess.run(
            ["curl", "-sL", "--max-time", "25", "-A", UA, url],
            capture_output=True, text=True, timeout=40)
    except Exception:
        return None
    m = re.search(r'<meta property="og:image" content="([^"]+)"', p.stdout)
    if not m:
        return None
    return m.group(1).replace("&amp;", "&")


def main():
    idx = json.load(open(IDX))
    try:
        thumbs = json.load(open(THUMBS))
    except Exception:
        thumbs = {}
    now = datetime.now(timezone.utc)
    fresh = {pid for pid, t in thumbs.items()
             if now - datetime.fromisoformat(t["fetched_at"]) < timedelta(days=STALE_DAYS)}
    todo = [r for r in idx["recipes"] if r["id"] not in fresh and r.get("link")]
    print(f"total={len(idx['recipes'])} fresh={len(fresh)} to_fetch={len(todo)}", flush=True)
    done = failed = 0
    for n, r in enumerate(todo):
        url = fetch_thumb(r["link"])
        if url:
            thumbs[r["id"]] = {"url": url, "fetched_at": now.isoformat()}
            done += 1
        else:
            # one retry after a breather
            time.sleep(8)
            url = fetch_thumb(r["link"])
            if url:
                thumbs[r["id"]] = {"url": url, "fetched_at": now.isoformat()}
                done += 1
            else:
                failed += 1
        if (n + 1) % 10 == 0:
            json.dump(thumbs, open(THUMBS, "w"))
            print(f"progress {n+1}/{len(todo)} done={done} failed={failed}", flush=True)
        time.sleep(3)
    json.dump(thumbs, open(THUMBS, "w"))
    print(f"DONE fetched={done} failed={failed}", flush=True)


if __name__ == "__main__":
    main()
