#!/usr/bin/env python3
"""Enrich thin posts (few detected ingredients) using their comments.

Creators often pin the full recipe in the comments. Merges newly detected
ingredient keywords, meal tags and attribute tags into data/index.json.
"""
import json, os, re, subprocess, sys, time
from collections import Counter

sys.path.insert(0, os.path.expanduser("~/workspace/instagram/food-recipes"))
sys.path.insert(0, os.path.expanduser("~/workspace/recipe-finder"))
from categorize import CATEGORIES
from build_index import hits, compute_tags, MEALS

ACCT = "17841405603303185"
IDX = os.path.expanduser("~/workspace/recipe-finder/data/index.json")
ENRICH = os.path.expanduser("~/workspace/recipe-finder/data/comment_enrich.json")
DROP = {"baking", "baked", "veg", "fruit", "dessert", "desserts", "mithai",
        "sweet dish", "sabzi", "sabji", "salt", "sugar", "pepper", "water"}


def fetch_batch(batch):
    """Fetch comments for a batch of post ids. Returns parsed JSON or None."""
    cmd = ["/opt/hatch/bin/instagram-cli", "fetch-post-comments",
           "--account-id", ACCT, "--post-ids", ",".join(batch), "--limit", "12"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def process_group(g, by_id, enrich):
    """Extract comment-derived data for one post into the enrich dict."""
    pid = g.get("media_id")
    rec = by_id.get(pid)
    if not rec:
        return False
    texts = [c.get("comment_text", "") for c in g.get("comments", []) or []]
    blob = " " + " ".join(texts).lower().replace("\n", " ") + " "
    new_ings = set()
    for _, kws in CATEGORIES:
        new_ings.update(hits(blob, kws))
    base_ings = set(rec["ingredients"])
    added = new_ings - base_ings
    entry = enrich.setdefault(pid, {"ingredients": [], "meals": [], "tags": []})
    changed = False
    if added:
        entry["ingredients"] = sorted(set(entry["ingredients"]) | added)
        changed = True
    for m, kws in MEALS:
        if m not in rec["meals"] and m not in entry["meals"] and hits(blob, kws):
            entry["meals"].append(m)
            changed = True
    for t in compute_tags(blob, base_ings | new_ings):
        if t not in rec["tags"] and t not in entry["tags"]:
            entry["tags"].append(t)
            changed = True
    if re.search(r"ingredient", blob):
        entry["recipe_in_comments"] = True
    return changed


def main():
    idx = json.load(open(IDX))
    recipes = idx["recipes"]
    by_id = {r["id"]: r for r in recipes}
    try:
        enrich = json.load(open(ENRICH))
    except Exception:
        enrich = {}
    thin = [r for r in recipes
            if len(r["ingredients"]) <= 3 and r["id"] not in enrich]
    print(f"thin posts: {len(thin)} (already enriched: {len(enrich)})", flush=True)
    ids = [r["id"] for r in thin]
    enriched = 0
    skipped = 0
    i = 0
    while i < len(ids):
        batch = ids[i:i + 5]
        data = fetch_batch(batch)
        if data is None:
            # retry once after a breather
            time.sleep(8)
            data = fetch_batch(batch)
        if data is None and len(batch) > 1:
            # split into singles to isolate the bad id
            for pid in batch:
                d1 = fetch_batch([pid])
                if d1 is None:
                    time.sleep(5)
                    d1 = fetch_batch([pid])
                if d1 is None:
                    skipped += 1
                    continue
                for g in d1.get("post_groups", []) or []:
                    if process_group(g, by_id, enrich):
                        enriched += 1
                time.sleep(2)
            i += len(batch)
            continue
        if data is None:
            skipped += len(batch)
            i += len(batch)
            continue
        for g in data.get("post_groups", []) or []:
            if process_group(g, by_id, enrich):
                enriched += 1
        i += len(batch)
        if i % 50 < 5:
            json.dump(enrich, open(ENRICH, "w"))
            print(f"progress {i}/{len(ids)}, enriched {enriched}, skipped {skipped}", flush=True)
        time.sleep(3)

    json.dump(enrich, open(ENRICH, "w"))
    print(f"DONE enriched={enriched} skipped={skipped} of {len(thin)}", flush=True)


if __name__ == "__main__":
    main()
