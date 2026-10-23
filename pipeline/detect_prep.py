#!/usr/bin/env python3
"""Prep-pill detection for the Recipe Finder.

Works ONLY from each recipe's own extracted text (recipe_ingredients /
recipe_method as merged into data/index.json):
  (a) an ingredient line that itself says soaked/marinated/fermented;
  (b) a Method sentence instructing soak/marinate/ferment/rest/thaw/proof
      of a specific ingredient — the pill attaches to the verb's direct
      object, never to every ingredient merely mentioned nearby.
Durations are taken from the recipe's own words (unit words normalized to
the approved sample's style: hrs / min); never invented. Ambiguous or
unsupported ties get no pill.
Output: ~/workspace/recipe-finder/data/prep_hints.json
  { recipe_id: { ingredient_line_index: "Prep · <label>" } }
Line indices match the page's ingLinesOf(): split on newlines, trim,
drop blanks.
"""
import json, re, sys
from collections import Counter

IDX = "/home/hatch/workspace/recipe-finder/data/index.json"
OUT = "/home/hatch/workspace/recipe-finder/data/prep_hints.json"
DEBUG = "--debug" in sys.argv

UNITS = {
    "cup", "cups", "tbsp", "tablespoon", "tablespoons", "tsp", "teaspoon",
    "teaspoons", "g", "gm", "gms", "gram", "grams", "kg", "ml", "l", "litre",
    "litres", "liter", "liters", "oz", "lb", "lbs", "pinch", "pinches",
    "handful", "can", "cans", "pack", "packet", "piece", "pieces", "clove",
    "cloves", "slice", "slices", "x",
}
DESCRIPTORS = {
    "fresh", "finely", "roughly", "thinly", "coarsely", "chopped", "diced",
    "sliced", "peeled", "grated", "crushed", "minced", "dried", "dry", "raw",
    "cooked", "boiled", "washed", "rinsed", "cleaned", "trimmed", "halved",
    "quartered", "soaked", "marinated", "fermented", "large", "small",
    "medium", "big", "hot", "cold", "warm", "soft", "hard", "ripe", "unripe",
    "boneless", "skinless", "deveined", "de-veined", "shelled", "hulled",
    "split", "broken", "powdered", "ground", "roasted", "toasted", "fried",
    "steamed", "frozen", "organic", "optional", "approx", "approximately",
    "whole",
}
STOP_HEADS = {"water", "oil"}

def split_lines(text):
    if not text:
        return []
    return [s.strip() for s in re.split(r"\r?\n+", text) if s.strip()]

def core_name(line):
    s = line.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = s.split(" or ")[0]
    s = re.sub(r"[@#]", " ", s)
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    toks = [t for t in s.split() if t]
    stop = {"for", "of", "the", "a", "an", "in", "with", "and", "&"}
    out = [t for t in toks
           if not re.fullmatch(r"[\d./]+", t) and t not in UNITS and t not in stop]
    while out and out[0] in DESCRIPTORS:
        out.pop(0)
    while out and out[-1] in DESCRIPTORS:
        out.pop()
    return " ".join(out)

def norm_unit(num, unit):
    u = unit.lower()
    if u.startswith("h"):
        return f"{num} hr" if num == "1" else f"{num} hrs"
    if u.startswith("m"):
        return f"{num} min"
    if u.startswith("s"):
        return f"{num} sec"
    return f"{num} day" if num == "1" else f"{num} days"

def find_duration(text):
    t = text.lower()
    cands = []
    m = re.search(r"\b(\d+(?:\.\d+)?(?:/\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?(?:/\d+)?)\s*(hours?|hrs?|minutes?|mins?|days?|seconds?|secs?)\b", t)
    if m:
        unit = m.group(3)
        u = "hrs" if unit.startswith("h") else ("min" if unit.startswith("m") else ("days" if unit.startswith("d") else "sec"))
        if u == "hrs" and m.group(2) == "1":
            u = "hr"
        if u == "days" and m.group(2) == "1":
            u = "day"
        cands.append((m.start(), f"{m.group(1)}–{m.group(2)} {u}"))
    m = re.search(r"\b(\d+(?:\.\d+)?(?:/\d+)?)\s*(hours?|hrs?|minutes?|mins?|days?|seconds?|secs?)\b", t)
    if m:
        cands.append((m.start(), norm_unit(m.group(1), m.group(2))))
    for pat, val in [(r"\bovernight\b", "overnight"),
                     (r"\bhalf an hour\b", "half an hour"),
                     (r"\ban hour\b", "an hour"),
                     (r"\ba few hours\b", "a few hours")]:
        m = re.search(pat, t)
        if m:
            cands.append((m.start(), val))
    if not cands:
        return None
    cands.sort()
    return cands[0][1]

PARTICIPLE_ACTION = {"soaked": "Soak", "marinated": "Marinate", "fermented": "Ferment"}
VERB_ACTION = [
    (re.compile(r"\b(soak|soaks|soaked|soaking)\b", re.I), "Soak"),
    (re.compile(r"\b(marinate|marinates|marinated|marinating)\b", re.I), "Marinate"),
    (re.compile(r"\b(ferment|ferments|fermented|fermenting)\b", re.I), "Ferment"),
    (re.compile(r"\b(thaw|thaws|thawed|thawing)\b", re.I), "Thaw"),
    (re.compile(r"\b(proof|proofs|proofed|proofing)\b", re.I), "Proof"),
    (re.compile(r"\b(rest|rests|rested|resting)\b", re.I), "Rest"),
]
AFTER_CUTS = [" in ", " with ", " for ", " until ", " overnight", " then",
              " before ", " at ", " on ", " to ", ";", " while ", " so ",
              " because ", " into ", " followed "]
PARTICIPLES = {"soaked", "marinated", "fermented", "thawed", "proofed", "rested"}
PART_CUTS = AFTER_CUTS + [",", " and ", " + "]
PRONOUN_ONLY = {"it", "them", "this", "that", "the", ""}

def match_in(segment, names, raw_word_lines=None):
    """Ingredient lines named in a short object segment. Full-phrase hits
    win; a head-noun hit counts only when unique — both among the lines'
    core names and among the raw line texts (a head word shared by two
    lines, e.g. almonds listed twice, is an ambiguous tie)."""
    full, head = [], []
    for idx, phrase, hd in names:
        if len(phrase) >= 3 and re.search(r"\b" + re.escape(phrase) + r"\b", segment):
            full.append(idx)
        elif len(hd) >= 3 and hd not in STOP_HEADS and \
                re.search(r"\b" + re.escape(hd) + r"\b", segment):
            head.append(idx)
    if full:
        hit_phrases = {p for i, p, _ in names if i in full}
        if all(len(p.split()) == 1 for p in hit_phrases) and len(hit_phrases) == 1:
            w = next(iter(hit_phrases))
            total = sum(1 for _, p, _ in names if w in p.split())
            if total > len(set(full)):
                return []  # the word names more lines than it matched
        return sorted(set(full))
    if head and len(set(head)) == 1:
        hd = names[[n[0] for n in names].index(head[0])][2]
        if raw_word_lines is not None and raw_word_lines.get(hd, 0) > 1:
            return []
        return head
    return []

def detect(recipe):
    lines = split_lines(recipe.get("recipe_ingredients"))
    method = recipe.get("recipe_method") or ""
    if not lines:
        return {}, []
    hints = {}
    evidence = []

    for i, line in enumerate(lines):
        if line.rstrip().endswith(":"):
            continue
        low = line.lower()
        m = re.search(r"\b(soaked|marinated|fermented)\b", low)
        if m:
            hints[i] = (PARTICIPLE_ACTION[m.group(1)], find_duration(low))
            evidence.append((i, "line", line))

    raw_word_lines = Counter()
    for line in lines:
        for w in set(re.findall(r"[a-z]+", line.lower())):
            raw_word_lines[w] += 1
    names = []
    for i, line in enumerate(lines):
        if line.rstrip().endswith(":"):
            continue
        cn = core_name(line)
        if cn and cn != "water":
            names.append((i, cn, cn.split()[-1]))

    sentences = []
    for step in split_lines(method):
        for s in re.split(r"(?<=[.!?])\s+", step):
            s = s.strip()
            if s:
                sentences.append(s)

    for sent in sentences:
        low = sent.lower()
        for verb_re, action in VERB_ACTION:
            for vm in verb_re.finditer(low):
                if action == "Proof" and re.match(r"\s*(bowl|pan|dish|basket|container|paper)\b", low[vm.end():vm.end() + 12]):
                    continue
                if low[vm.end():vm.end() + 3].startswith(" up"):
                    continue  # 'soak up the sauce' = absorb, not prep
                if action == "Rest":
                    if re.match(r"\s+of\b", low[vm.end():]):
                        continue
                    if not re.search(r"\b(let|allow|leave|keep|set)\b[^.]{0,60}$", low[:vm.start()]) \
                       and not re.match(r"\s+(the|it|dough|batter)\b", low[vm.end():]) \
                       and "to rest" not in low:
                        continue
                targets = []
                skip_cue = False
                # construction 1: let/allow/leave <object> <verb>
                mlet = None
                for lm in re.finditer(r"\b(let|allow|leave)\b", low[:vm.start()]):
                    mlet = lm
                if mlet and vm.start() - mlet.end() <= 60:
                    seg = low[mlet.end():vm.start()]
                    if seg.strip(" ,") in PRONOUN_ONLY or \
                       seg.strip().split()[:1] in (["it"], ["them"]):
                        skip_cue = True
                    else:
                        targets = match_in(seg, names, raw_word_lines)
                if skip_cue:
                    continue
                # construction 2: <verb> <object> ...
                if not targets:
                    after = low[vm.end():vm.end() + 80]
                    vform = vm.group(1)
                    cuts = PART_CUTS if (vform in PARTICIPLES or vform.endswith("ing")) else AFTER_CUTS
                    cut = len(after)
                    for c in cuts:
                        p = after.find(c)
                        if p != -1:
                            cut = min(cut, p)
                    seg = after[:cut].strip(" ,")
                    first = seg.split()[:1]
                    if first and first[0].strip(").,") in ("it", "them", "this", "that", "itself"):
                        continue  # anaphoric object: names no ingredient line
                    if seg not in PRONOUN_ONLY:
                        targets = match_in(seg, names, raw_word_lines)
                # construction 3: <object> <verb> (passive / participle)
                if not targets:
                    before = low[max(0, vm.start() - 45):vm.start()]
                    bcut = max(before.rfind(","), before.rfind(";"),
                               before.rfind(" and "), before.rfind(" then "),
                               before.rfind(" followed by "))
                    seg = before[bcut:] if bcut != -1 else before
                    if " if " not in seg:
                        targets = match_in(seg.strip(" ,"), names, raw_word_lines)
                if not targets:
                    continue
                # duration: the verb's own clause — from the verb to the
                # next 'then'/clause break, plus a small look-behind for
                # 'overnight soaked X' style phrasing.
                win = low[vm.start():]
                tp = win.find(" then")
                if tp != -1:
                    win = win[:tp]
                sm = re.search(r"\s(and|then)\s+(cook|bake|fry|add|heat|boil|simmer|serve|mix|blend|stir|grill|roast|pressure|preheat)\b", win)
                if sm:
                    win = win[:sm.start()]
                dur = find_duration(win[:110]) or \
                    find_duration(low[max(0, vm.start() - 30):vm.start()])
                for idx in targets:
                    if idx in hints:
                        a0, d0 = hints[idx]
                        if a0 == action and not d0 and dur:
                            hints[idx] = (action, dur)
                        continue
                    hints[idx] = (action, dur)
                    evidence.append((idx, "method", sent))
    labels = {i: "Prep · " + a + (f" {d}" if d else "")
              for i, (a, d) in hints.items()}
    return labels, evidence

def main():
    idx = json.load(open(IDX))
    out = {}
    total = 0
    dist = Counter()
    titles = {r["id"]: r["title"] for r in idx["recipes"]}
    byid = {r["id"]: r for r in idx["recipes"]}
    for r in idx["recipes"]:
        h, ev = detect(r)
        if h:
            out[r["id"]] = {str(k): v for k, v in sorted(h.items())}
            total += len(h)
            for v in h.values():
                dist[v] += 1
            if DEBUG:
                lines = split_lines(r.get("recipe_ingredients"))
                for idx_i, kind, txt in ev:
                    print(f"[{r['title']}] line {idx_i} {h[idx_i]!r} <- {kind}: {txt!r} || ing: {lines[idx_i]!r}")
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"recipes with >=1 pill: {len(out)}")
    print(f"total pills: {total}")
    print("label distribution:")
    for label, n in dist.most_common():
        print(f"  {n:4d}  {label}")

if __name__ == "__main__":
    main()
