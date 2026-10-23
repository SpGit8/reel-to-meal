#!/usr/bin/env python3
"""Build a compact searchable index of the saved 'Food Recipes' posts.

Output: ~/workspace/recipe-finder/data/index.json
  { "meta": { "total": N, "top_ingredients": [...] },
    "recipes": [ {id, title, author, link, category, ingredients[], meals[]} ] }
"""
import json, os, re, glob, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.expanduser("~/workspace/instagram/food-recipes"))
from categorize import CATEGORIES, assign_category  # noqa: E402

PAGES = os.path.expanduser("~/workspace/instagram/food-recipes/pages")
OUTDIR = os.path.expanduser("~/workspace/recipe-finder/data")
os.makedirs(OUTDIR, exist_ok=True)

MEALS = [
    ("breakfast", ["breakfast", "brunch", "morning breakfast", "breakfast recipe"]),
    ("lunch", ["lunch", "lunchbox", "lunch box", "tiffin"]),
    ("dinner", ["dinner", "supper", "dinner recipe"]),
    ("snack", ["snack", "snacks", "evening snack", "tea time", "teatime", "appetizer",
               "appetiser", "starter", "starters", "finger food"]),
    ("dessert", ["dessert", "desserts", "mithai"]),
]

OTHER = "Other / unclear"

TAG_RULES = [
    ("meal prep friendly", ["meal prep", "mealprep", "meal-prep", "make ahead", "make-ahead",
     "batch cook", "batch-cook", "prep ahead", "prep-ahead"]),
    ("quick", ["15 min", "15-minute", "15 minute", "20 min", "20-minute", "20 minute",
     "30 min", "30-minute", "30 minute", "10 min", "10-minute", "weeknight",
     "5 ingredient", "5-ingredient", "quick and easy"]),
    ("one pot", ["one pot", "one-pot", "one pan", "one-pan", "sheet pan", "sheet-pan"]),
    ("kid friendly", ["kid friendly", "kid-friendly", "kids love", "toddler",
     "baby friendly", "baby-friendly", "lunchbox"]),
    ("postpartum friendly", ["postpartum", "post-partum", "post partum", "postnatal"]),
    ("menstruation friendly", ["menstru", "menstrual", "period pain", "period pains",
     "pms", "seed cycling", "cycle syncing", "iron rich", "iron-rich", "rich in iron",
     "during your period", "period friendly"]),
]

STRONG_PROTEIN = ["chicken", "paneer", "tofu", "tempeh", "egg", "eggs", "chickpea",
    "chickpeas", "chana", "lentil", "lentils", "dal", "moong", "masoor", "fish", "salmon",
    "tuna", "shrimp", "prawn", "prawns", "greek yogurt", "greek yoghurt", "quinoa",
    "edamame", "turkey"]

MEAT_FISH = ["chicken", "beef", "pork", "bacon", "fish", "salmon", "tuna", "shrimp",
    "prawn", "prawns", "crab", "lobster", "mutton", "lamb", "turkey", "sausage", "ham",
    "meat", "keema", "pepperoni", "surmai", "rohu", "pomfret"]
ANIMAL = MEAT_FISH + ["milk", "butter", "ghee", "cheese", "paneer", "cream", "yogurt",
    "yoghurt", "dahi", "curd", "egg", "eggs", "honey", "gelatin"]


def compute_tags(text, ingredients):
    tags = []
    for name, kws in TAG_RULES:
        if hits(text, kws):
            tags.append(name)
    if hits(text, ["high protein", "high-protein", "protein rich", "protein-rich",
                   "protein packed", "protein-packed"]) or hits(text, STRONG_PROTEIN):
        tags.append("high protein")
    # Animal evidence (caption text or detected ingredients) always vetoes a
    # vegan/vegetarian label — a hashtag claim never beats turkey in the dish.
    animal_hit = bool(hits(text, ANIMAL)) or bool(set(ingredients) & set(ANIMAL))
    meat_hit = bool(hits(text, MEAT_FISH)) or bool(set(ingredients) & set(MEAT_FISH))
    if not animal_hit and ("vegan" in text or ingredients):
        tags.append("vegan")
    elif not meat_hit and (hits(text, ["vegetarian", "pure veg", "veg recipe",
                                        "shakahari"]) or ingredients):
        tags.append("vegetarian")
    return tags


def hits(text, keywords):
    found = []
    for kw in keywords:
        if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text):
            found.append(kw)
    return found


def main():
    seen = set()
    recipes = []
    ing_counter = Counter()
    for f in sorted(glob.glob(os.path.join(PAGES, "page-*.json"))):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        for p in data.get("posts", []) or []:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            cap = p.get("caption")
            cap_text = cap.get("text", "") if isinstance(cap, dict) else (cap or "")
            text = " " + cap_text.lower().replace("\n", " ") + " "

            ingredients = set()
            for name, kws in CATEGORIES:
                ingredients.update(hits(text, kws))
            # category: real main ingredients beat pantry staples (two-pass)
            best = assign_category(text, lambda t, kws: len(hits(t, kws)))

            meals = [m for m, kws in MEALS if hits(text, kws)]

            first = ""
            for line in cap_text.split("\n"):
                if line.strip():
                    first = line.strip()
                    break
            title = first[:120] or "Untitled recipe"

            ing_list = sorted(ingredients)
            tags = compute_tags(text, set(ing_list))

            # full caption prose (hashtags/handles stripped) for secondary
            # free-text matching on the page
            clean = re.sub(r"#[A-Za-z0-9_]+|@[A-Za-z0-9_.]+", " ", cap_text)
            recipes.append({
                "id": pid,
                "title": title,
                "author": (p.get("user") or {}).get("username", ""),
                "link": p.get("permalink", ""),
                "category": best,
                "ingredients": ing_list,
                "meals": meals,
                "tags": tags,
                "text": re.sub(r"\s+", " ", clean.lower()).strip()[:1500],
                "caption": cap_text.strip()[:4000],
            })

    # merge comment-derived enrichment (persistent across rebuilds)
    try:
        enrich = json.load(open(os.path.join(OUTDIR, "comment_enrich.json")))
    except Exception:
        enrich = {}
    # merge video-summary-derived claim tags (persistent across rebuilds)
    try:
        venrich = json.load(open(os.path.join(OUTDIR, "video_enrich.json")))
    except Exception:
        venrich = {}
    for pid, extra in venrich.items():
        cur = enrich.setdefault(pid, {})
        cur["tags"] = sorted(set(cur.get("tags", [])) | set(extra.get("tags", [])))
    by_id = {r["id"]: r for r in recipes}
    for pid, extra in enrich.items():
        r = by_id.get(pid)
        if not r:
            continue
        r["ingredients"] = sorted(set(r["ingredients"]) | set(extra.get("ingredients", [])))
        r["meals"] = sorted(set(r["meals"]) | set(extra.get("meals", [])))
        r["tags"] = sorted(set(r["tags"]) | set(extra.get("tags", [])))
        if extra.get("recipe_in_comments"):
            r["recipe_in_comments"] = True

    # judged time-of-day meals (owner-approved pass, 2026-10-20) replace the
    # keyword meals outright for judged recipes; unjudged recipes keep the
    # keyword result until they are judged
    try:
        meals_judged = json.load(open(os.path.join(OUTDIR, "meals_judged.json")))
    except Exception:
        meals_judged = {}
    for r in recipes:
        if r["id"] in meals_judged:
            r["meals"] = sorted(meals_judged[r["id"]])

    # Verbatim recipe extracts are loaded here, ahead of their merge below,
    # because comment recipe texts now live on the extract entries
    # themselves — the comment_text field, folded in from the retired
    # data/comment_recipes.json on 2026-10-23.
    try:
        recipe_extracts = json.load(open(os.path.join(OUTDIR, "recipe_extracts.json")))
    except Exception:
        recipe_extracts = {}
    # merge comment recipe texts (full recipe pulled from a post's comments,
    # kept for recipe previews)
    for pid, entry in recipe_extracts.items():
        r = by_id.get(pid)
        if r and entry.get("comment_text"):
            r["comment_recipe"] = entry["comment_text"]

    # merge verbatim recipe extracts (ingredients + method pulled from the
    # caption text; previews show these instead of the raw caption) —
    # recipe_extracts was already loaded above
    for pid, entry in recipe_extracts.items():
        r = by_id.get(pid)
        if r:
            if entry.get("ingredients"):
                r["recipe_ingredients"] = entry["ingredients"]
            if entry.get("method"):
                r["recipe_method"] = entry["method"]
            if entry.get("source"):
                r["extract_source"] = entry["source"]

    # dish-type overrides (semantic classification: Soups / Sides & Dips /
    # Snacks), explicit per-recipe exceptions, and the end of Pantry as an
    # assignable category — leftovers land in Other / unclear.
    try:
        dish_types = json.load(open(os.path.join(OUTDIR, "dish_types.json")))
    except Exception:
        dish_types = {}
    try:
        dish_exc = json.load(open(os.path.join(OUTDIR, "dish_exceptions.json")))
    except Exception:
        dish_exc = {}
    # semantic dish-identity labels (persistent across rebuilds)
    try:
        semantic = json.load(open(os.path.join(OUTDIR, "semantic_categories.json")))
    except Exception:
        semantic = {}
    PANTRY = "Pantry, Spices & Condiments"
    for r in recipes:
        if r["id"] in dish_exc:
            r["category"] = dish_exc[r["id"]]
        elif r["id"] in dish_types:
            r["category"] = dish_types[r["id"]]
        elif r["id"] in semantic:
            r["category"] = semantic[r["id"]]
        if r["category"] == PANTRY:
            r["category"] = OTHER

    # Final veto on merged tags (comment/video enrichment can re-add claims):
    # positive animal-ingredient evidence beats any vegan/vegetarian tag.
    for r in recipes:
        ing = set(r["ingredients"])
        if "vegan" in r["tags"] and ing & set(ANIMAL):
            r["tags"] = [t for t in r["tags"] if t != "vegan"]
            if not (ing & set(MEAT_FISH)) and "vegetarian" not in r["tags"]:
                r["tags"] = sorted(r["tags"] + ["vegetarian"])
        if "vegetarian" in r["tags"] and ing & set(MEAT_FISH):
            r["tags"] = [t for t in r["tags"] if t != "vegetarian"]

    # Feature-based group membership: a recipe belongs to an ingredient
    # group only when the ingredient is a FEATURE of the dish. An ingredient
    # that appears in the caption only in a seasoning form (lemon juice,
    # sesame oil, olive oil) never confers membership; an ingredient named
    # in the title always does; universal aromatics (onion, garlic, ginger)
    # confer it only via the title. Search and ingredient lists are untouched.
    SEASON_WORDS = {"juice", "juices", "oil", "oils", "zest", "juiced"}
    AROMATICS = {"onion", "onions", "garlic", "ginger", "green chili",
                 "green chilli", "green chillies"}
    SENT_SPLIT = re.compile(r"[.!?;\n]+")

    def is_feature(r, kw):
        title = " " + (r["title"] or "").lower() + " "
        pat = re.compile(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])")
        if pat.search(title):
            return True
        if kw in AROMATICS:
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
            return True
        return False

    for r in recipes:
        groups = []
        for name, kws in CATEGORIES:
            if name == PANTRY:
                continue
            title = " " + (r["title"] or "").lower() + " "
            if any(hits(title, [kw]) for kw in kws) or \
               any(is_feature(r, kw) for kw in kws if kw in r["ingredients"]):
                groups.append(name)
        r["groups"] = sorted(groups)

    # count ingredients across the final (enriched) recipes for the chips row
    ing_counter = Counter()
    for r in recipes:
        ing_counter.update(set(r["ingredients"]))

    # Clean chip list: merge simple plurals, drop method/generic words
    DROP = {"baking", "baked", "veg", "fruit", "dessert", "desserts", "mithai",
            "sweet dish", "sabzi", "sabji", "salt", "sugar", "pepper", "water"}
    merged = Counter()
    for w, c in ing_counter.items():
        key = w
        if w.endswith("s") and w[:-1] in ing_counter:
            key = w[:-1]
        if key not in DROP:
            merged[key] += c
    top_ingredients = [w for w, _ in merged.most_common(24)]

    index = {"meta": {"total": len(recipes), "top_ingredients": top_ingredients},
             "recipes": recipes}
    with open(os.path.join(OUTDIR, "index.json"), "w") as f:
        json.dump(index, f)
    size_kb = os.path.getsize(os.path.join(OUTDIR, "index.json")) // 1024
    print(f"DONE recipes={len(recipes)} index_size={size_kb}KB", flush=True)
    print("top ingredients:", ", ".join(top_ingredients[:15]), flush=True)


if __name__ == "__main__":
    main()
