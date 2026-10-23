#!/usr/bin/env python3
"""Fetch the actual recipe text from comments for recipe_in_comments posts.

The enrichment pass extracted ingredients from comments but discarded the
text. For the 22 posts flagged recipe_in_comments, fetch the comments once
more and keep the recipe comment's full text in data/comment_recipes.json so
recipe previews can show it. Stops immediately on any fetch failure (the
account was rate-limited earlier tonight); partial progress is saved.
"""
import json, os, re, subprocess, sys, time

ACCT = "17841405603303185"
BASE = os.path.expanduser("~/workspace/recipe-finder/data")
ENRICH = os.path.join(BASE, "comment_enrich.json")
OUT = os.path.join(BASE, "comment_recipes.json")
IDX = os.path.join(BASE, "index.json")


def fetch_batch(batch):
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


def pick_recipe_text(comments, author):
    """Score comments; the recipe is usually the author's long comment that
    lists ingredients/measurements."""
    best, best_score = "", -1
    for c in comments:
        t = (c.get("comment_text") or "").strip()
        if len(t) < 120:
            continue
        low = t.lower()
        score = len(t) / 500.0
        if "ingredient" in low:
            score += 3
        if re.search(r"\d\s*(cup|cups|tbsp|tsp|g\b|kg|ml|oz|tablespoon|teaspoon)", low):
            score += 2
        if c.get("username") and author and c["username"] == author:
            score += 2
        if t.count("\n") >= 3:
            score += 1
        if score > best_score:
            best, best_score = t, score
    return best


def main():
    enrich = json.load(open(ENRICH))
    idx = json.load(open(IDX))
    authors = {r["id"]: None for r in idx["recipes"]}
    # author usernames are stripped from the index; recover from source pages
    import glob
    for f in glob.glob(os.path.expanduser(
            "~/workspace/instagram/food-recipes/pages/*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for p in d.get("posts", []):
            u = (p.get("user") or {}).get("username")
            if p.get("id") in authors and u:
                authors[p["id"]] = u
    flagged = [pid for pid, v in enrich.items()
               if isinstance(v, dict) and v.get("recipe_in_comments")]
    print(f"flagged posts: {len(flagged)}", flush=True)
    try:
        saved = json.load(open(OUT))
    except Exception:
        saved = {}
    todo = [p for p in flagged if p not in saved]
    print(f"to fetch: {len(todo)}", flush=True)
    stopped = False
    i = 0
    while i < len(todo):
        batch = todo[i:i + 5]
        data = fetch_batch(batch)
        if data is None:
            print("FETCH FAILED — stopping (possible rate limit)", flush=True)
            stopped = True
            break
        groups = {g.get("media_id"): g for g in data.get("post_groups", []) or []}
        for pid in batch:
            g = groups.get(pid)
            comments = (g.get("comments") if g else None) or []
            text = pick_recipe_text(comments, authors.get(pid))
            if text:
                saved[pid] = {"text": text[:4000], "chars": len(text)}
                print(f"  saved recipe text for {pid} ({len(text)} chars)", flush=True)
            else:
                print(f"  no recipe-like comment found for {pid}", flush=True)
        i += len(batch)
        if i < len(todo):
            time.sleep(3)
    json.dump(saved, open(OUT, "w"))
    print(f"DONE saved={len(saved)} stopped_early={stopped}", flush=True)


if __name__ == "__main__":
    main()
