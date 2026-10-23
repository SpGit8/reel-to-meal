#!/usr/bin/env python3
"""Compute feature-based group membership for every recipe in index.json.

Run AFTER build_index.py and after short titles have been re-applied:
group membership must be judged against the SHORT title (the recipe's
name), not the long caption first-line the builder starts from.

Rule: a recipe belongs to an ingredient group only when the ingredient
is a FEATURE of the dish. An ingredient that appears in the caption only
in a seasoning form (lemon juice, sesame oil, olive oil) never confers
membership; an ingredient named in the (short) title always does;
universal aromatics (onion, garlic, ginger) confer it only via the title.
Search and ingredient lists are untouched.
"""
import json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.expanduser("~/workspace/instagram/food-recipes"))
from categorize import CATEGORIES  # noqa: E402

IDX = os.path.expanduser("~/workspace/recipe-finder/data/index.json")
PANTRY = "Pantry, Spices & Condiments"
SEASON_WORDS = {"juice", "juices", "oil", "oils", "zest", "juiced"}
AROMATICS = {"onion", "onions", "garlic", "ginger", "green chili",
             "green chilli", "green chillies", "spring onion", "spring onions",
             "scallion", "scallions"}
# Keywords that name a method or dish form rather than an ingredient;
# they never confer group membership on their own.
METHOD_WORDS = {"stir fry", "stir-fry"}
# Drink bases: in "powder" form (espresso powder in a cake batter) they are a
# flavor enhancer, not a drink — powder mentions never confer membership.
DRINK_BASES = {"coffee", "espresso", "cappuccino", "matcha", "chai"}
SENT_SPLIT = re.compile(r"[.!?;\n]+")


def hits(text, keywords):
    return [kw for kw in keywords
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text)]


def is_feature(r, kw):
    if kw in METHOD_WORDS:
        return False
    title = " " + (r["title"] or "").lower() + " "
    pat = re.compile(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])")
    if pat.search(title):
        return True
    if kw in AROMATICS:
        return False
    if kw in METHOD_WORDS:
        return False
    if SEASON_WORDS & set(kw.split()):
        return False
    body = r["text"] or ""
    for m in pat.finditer(body):
        start = max([m2.end() for m2 in SENT_SPLIT.finditer(body[:m.start()])] or [0])
        ends = [m2.start() for m2 in SENT_SPLIT.finditer(body, m.end())]
        sentence = body[start:(ends[0] if ends else len(body))].lower()
        after = re.findall(r"[a-z]+", body[m.end():m.end() + 24])
        if any(w in SEASON_WORDS for w in re.findall(r"[a-z]+", sentence)):
            continue  # this mention is a seasoning form; keep looking
        if after[:2] and any(w in SEASON_WORDS for w in after[:2]):
            continue
        if kw == "soy" and after[:1] == ["sauce"]:
            continue  # soy sauce is a seasoning, not a soy dish
        if kw in DRINK_BASES and after[:1] == ["powder"]:
            continue  # espresso powder in a batter is a flavoring, not a drink
        return True
    return False


def main():
    idx = json.load(open(IDX))
    for r in idx["recipes"]:
        groups = []
        for name, kws in CATEGORIES:
            if name == PANTRY:
                continue
            title = " " + (r["title"] or "").lower() + " "
            if any(hits(title, [kw]) for kw in kws) or \
               any(is_feature(r, kw) for kw in kws if kw in r["ingredients"]):
                groups.append(name)
        r["groups"] = sorted(groups)
    with open(IDX, "w") as f:
        json.dump(idx, f)
    cnt = Counter()
    for r in idx["recipes"]:
        for g in r["groups"]:
            cnt[g] += 1
    print("groups recomputed for", len(idx["recipes"]), "recipes")
    for name, c in cnt.most_common():
        print(name, ":", c)


if __name__ == "__main__":
    main()
