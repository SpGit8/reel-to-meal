#!/usr/bin/env python3
"""Fetch Instagram media-understanding summaries for all saved recipe posts.

Persistent: writes ~/workspace/recipe-finder/data/video_summaries.json
(id -> {summary}). Skips ids already stored. STOPS ALL INSTAGRAM ACCESS
on any 429 / rate-limit signal, keeping partial progress.
"""
import json, os, subprocess, sys, time

BASE = os.path.expanduser("~/workspace/recipe-finder")
DATA = os.path.join(BASE, "data")
STORE = os.path.join(DATA, "video_summaries.json")
CLI = "/opt/hatch/bin/instagram-cli"
ACCOUNT = "17841405603303185"
BATCH = 25
PAUSE = 2.0


def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def seed_from_pilots(store):
    for f in ("pilot-mu-1.json", "pilot-mu-2.json"):
        try:
            data = json.load(open(os.path.join(BASE, f)))
        except Exception:
            continue
        for m in data.get("media", []) or []:
            mid = m.get("media_id")
            if mid and mid not in store:
                store[mid] = {"summary": (m.get("narrative_summary") or "").strip() or None}


def main():
    idx = load(os.path.join(DATA, "index.json"), {})
    ids = [r["id"] for r in idx.get("recipes", [])]
    store = load(STORE, {})
    seed_from_pilots(store)

    todo = [i for i in ids if i not in store]
    print(f"total={len(ids)} have={len(store)} todo={len(todo)}", flush=True)

    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        try:
            proc = subprocess.run(
                [CLI, "media-understanding", "--account-id", ACCOUNT,
                 "--media-ids", ",".join(chunk)],
                capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT at batch starting {start} — stopping, progress saved", flush=True)
            break
        out = (proc.stdout or "") + (proc.stderr or "")
        # Real rate-limit signals only: nonzero exit, or an explicit
        # rate-limit message in stderr. (Summary TEXT can contain "429"
        # as a number — never scan payloads for it.)
        if proc.returncode != 0 or "Too Many Requests" in (proc.stderr or ""):
            print(f"RATE LIMIT / error at batch {start}: rc={proc.returncode}", flush=True)
            print(out[:500], flush=True)
            print("STOPPING all Instagram access; partial progress kept", flush=True)
            break
        try:
            data = json.loads(proc.stdout)
        except Exception:
            print(f"BAD JSON at batch {start} — stopping", flush=True)
            break
        media_items = data.get("media", []) or []
        errs = [m for m in media_items if m.get("error")]
        if media_items and len(errs) == len(media_items):
            print(f"ALL ITEMS ERRORED at batch {start}: {str(errs[0].get('error'))[:200]}", flush=True)
            print("STOPPING; partial progress kept", flush=True)
            break
        for m in data.get("media", []) or []:
            mid = m.get("media_id")
            if mid:
                store[mid] = {"summary": (m.get("narrative_summary") or "").strip() or None}
        json.dump(store, open(STORE, "w"))
        got = sum(1 for c in chunk if c in store)
        print(f"batch {start//BATCH+1}: stored {got}/{len(chunk)} (total {len(store)})", flush=True)
        time.sleep(PAUSE)

    json.dump(store, open(STORE, "w"))
    filled = sum(1 for v in store.values() if v.get("summary"))
    print(f"DONE have={len(store)} with_summary={filled} empty={len(store)-filled}", flush=True)


if __name__ == "__main__":
    main()
