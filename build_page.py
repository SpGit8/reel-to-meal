#!/usr/bin/env python3
"""Build the Recipe Finder page (index.html) from committed data + template.

The page's design/code lives in page/template.html — the Muse artifact's
exported page with its data payloads replaced by placeholders. The data
payloads are regenerated here from data/*.json, so a data-only commit is
enough to produce an updated page:

  /*__INDEX__*/   <- data/index.json, minus each recipe's author/caption
  /*__QUANT__*/   <- data/quantities.json, compacted (see page_quant)
  /*__CUISINE__*/ <- data/cuisine_judged.json, unclassified (null) dropped
  /*__PREP__*/    <- data/prep_hints.json, verbatim
  <!--__CARDS__--> <- static pre-rendered cards, one per recipe, with the
                      192x192 WebP thumbnails generated from assets/thumbs/

To refresh the template after the Muse artifact page changes design, run:

  python3 build_page.py --extract path/to/fresh-export.html

which rewrites page/template.html from that export. Then commit the new
template together with the data files.
"""

import base64
import html as htmllib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "page", "template.html")
OUT = os.path.join(ROOT, "index.html")
DATA = os.path.join(ROOT, "data")
THUMB_DIR = os.path.join(ROOT, "assets", "thumbs")

BLOBS = ["INDEX", "QUANT", "CUISINE", "PREP"]
INDEX_KEY_ORDER = [
    "category", "extract_source", "groups", "id", "ingredients", "link",
    "meals", "recipe_ingredients", "recipe_method", "tags", "text", "title",
]


def load_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- payloads

def page_index(index):
    """index.json as embedded in the page: author/caption stripped (her
    call — author names never ship in the page), everything else verbatim."""
    recipes = [
        {k: r[k] for k in INDEX_KEY_ORDER if k in r}
        for r in index["recipes"]
    ]
    return {"meta": index["meta"], "recipes": recipes}


def _num(x):
    x = round(float(x), 4)
    return int(x) if x.is_integer() else x


def _js_len(s):
    """JavaScript String.length (UTF-16 code units), which is what the
    page's scaler data was built with."""
    return len(s.encode("utf-16-le")) // 2


def page_quant(quantities):
    """Compact quantities.json into the page's scaler format:
    {id: [base, baseStated(1/0), [[lineIdx, lo, hi?, restLen], ...]]}."""
    out = {}
    for rid, entry in quantities.items():
        lines = []
        for i, line in enumerate(entry["lines"]):
            qty = line.get("qty")
            if not qty:
                continue
            item = [i, _num(qty[0])]
            if len(qty) > 1 and qty[1] is not None:
                item.append(_num(qty[1]))
            item.append(_js_len(line["rest"]))
            lines.append(item)
        out[rid] = [_num(entry["base"]), 1 if entry["base_stated"] else 0, lines]
    return out


def page_cuisine(cuisine_judged):
    return {k: v for k, v in cuisine_judged.items() if v}


# ------------------------------------------------------------------- cards

def webp_data_uri(jpg_path):
    from PIL import Image

    im = Image.open(jpg_path).convert("RGB")
    w, h = im.size
    side = min(w, h)
    im = im.crop(((w - side) // 2, (h - side) // 2,
                  (w + side) // 2, (h + side) // 2))
    im = im.resize((192, 192), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=68)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def card_html(recipe, quant_ids, group_rank):
    """Render one static card exactly as the artifact's pre-render does.

    `recipe` is the raw data/index.json entry: the static cards also use
    its recipe_in_comments flag, which the embedded INDEX blob drops."""
    rid = recipe["id"]
    thumb_path = os.path.join(THUMB_DIR, rid + ".jpg")
    has_photo = os.path.exists(thumb_path)
    # "Full recipe": exact quantities parsed AND a written method.
    is_full = rid in quant_ids and bool(recipe.get("recipe_method"))
    parts = ['<article class="card" data-id="%s">' % rid]
    if has_photo:
        parts.append(
            '<img class="thumb" loading="lazy" decoding="async" alt="" '
            'src="%s">' % webp_data_uri(thumb_path)
        )
        if is_full:
            parts.append('<span class="mdot" title="Full recipe"></span>')
    parts.append("<h3>%s</h3>" % htmllib.escape(recipe["title"], quote=False))
    # Badges: the category first, then the recipe's ingredient groups in
    # the page's canonical INGREDIENT_GROUPS order, category not repeated.
    # A recipe whose category is "Other / unclear" shows its first group
    # as the primary badge instead (the category badge appears only when
    # the recipe has no groups at all).
    alt_groups = [g for g in recipe["groups"] if g != recipe["category"]]
    alt_groups.sort(key=lambda g: (group_rank.get(g, len(group_rank)),
                                   recipe["groups"].index(g)))
    if recipe["category"] == "Other / unclear" and alt_groups:
        display = alt_groups
    else:
        display = [recipe["category"]] + alt_groups
    badges = "".join(
        '<span class="badge%s">%s</span>'
        % ("" if i == 0 else " alt", htmllib.escape(g, quote=False))
        for i, g in enumerate(display)
    )
    if is_full and not has_photo:
        # Thumbnail-less full recipes carry the dot inline in the meta row.
        badges = '<span class="mdot inl" title="Full recipe"></span>' + badges
    parts.append('<div class="meta">%s</div>' % badges)
    bits = []
    if recipe["meals"]:
        bits.append(", ".join(recipe["meals"]))
    if recipe["tags"]:
        bits.append(" ".join("#" + t for t in recipe["tags"]))
    if bits:
        parts.append('<div class="tagline">%s</div>'
                     % htmllib.escape(" · ".join(bits), quote=False))
    if recipe.get("recipe_in_comments"):
        parts.append('<div class="cnote">Full recipe in the post\'s '
                     'comments</div>')
    parts.append(
        '<a class="iglink" href="%s" target="_blank" rel="noopener" '
        'aria-label="Open on Instagram" title="Open on Instagram"></a>'
        % htmllib.escape(recipe["link"], quote=True)
    )
    parts.append("</article>")
    return "".join(parts)


# ------------------------------------------------------------------- build

def build():
    template = open(TPL, encoding="utf-8").read()
    for name in BLOBS:
        ph = "/*__%s__*/null" % name
        assert template.count(ph) == 1, "placeholder %s missing" % ph
    assert template.count("<!--__CARDS__-->") == 1, "cards placeholder missing"

    index = load_json("index.json")
    payloads = {
        "INDEX": page_index(index),
        "QUANT": page_quant(load_json("quantities.json")),
        "CUISINE": page_cuisine(load_json("cuisine_judged.json")),
        "PREP": load_json("prep_hints.json"),
    }
    quant_ids = set(payloads["QUANT"])

    # Canonical ingredient-group order, read from the template itself so
    # badge order follows the page's own taxonomy.
    m = re.search(r"const INGREDIENT_GROUPS = (\[.*?\]);", template, re.S)
    canonical = json.loads(m.group(1)) if m else []
    group_rank = {g: i for i, g in enumerate(canonical)}

    page = template
    for name, payload in payloads.items():
        page = page.replace("/*__%s__*/null" % name, dumps(payload))
    cards = "\n".join(
        card_html(r, quant_ids, group_rank)
        for r in index["recipes"]
    )
    page = page.replace("<!--__CARDS__-->", cards)

    total = payloads["INDEX"]["meta"]["total"]
    page = re.sub(r'(<p id="sub">)[\d,]+ saved recipes',
                  r"\g<1>%s saved recipes" % f"{total:,}", page)
    page = re.sub(r"Browsing [\d,]+ recipes",
                  "Browsing %s recipes" % f"{total:,}", page)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("built %s: %d recipes, %.1f MB"
          % (OUT, len(payloads["INDEX"]["recipes"]), len(page) / 1e6))


# ----------------------------------------------------------------- extract

def _json_span(text, start):
    """Return (value, end_index) for the JSON value starting at `start`."""
    return json.JSONDecoder().raw_decode(text, start)


def extract(export_path):
    text = open(export_path, encoding="utf-8").read()
    spans = []  # (start, end, replacement)

    for name in BLOBS:
        marker = "const %s = " % name
        at = text.find(marker)
        assert at >= 0, "blob %s not found in export" % name
        vstart = at + len(marker)
        _, vend = _json_span(text, vstart)
        assert text[vend] == ";", "blob %s not terminated by ;" % name
        spans.append((vstart, vend, "/*__%s__*/null" % name))

    div = '<div id="results">'
    dat = text.find(div)
    assert dat >= 0, "results div not found"
    cstart = dat + len(div)
    # The static cards form one contiguous run (separated only by
    # whitespace) starting just after the results div. The page's JS also
    # contains "<article" strings, but those are not contiguous with it.
    starts = [m.start() for m in re.finditer(r'<article class="card"', text)
              if m.start() >= cstart]
    assert starts, "no static cards found"
    end = None
    count = 0
    for s in starts:
        if end is not None and text[end:s].strip():
            break
        end = text.find("</article>", s) + len("</article>")
        count += 1
    assert count >= 1000, "too few static cards: %d" % count
    spans.append((starts[0], end, "<!--__CARDS__-->"))

    for start, end, repl in sorted(spans, reverse=True):
        text = text[:start] + repl + text[end:]
    with open(TPL, "w", encoding="utf-8") as f:
        f.write(text)
    print("template written to %s (%.1f KB, %d inline webp left in code)"
          % (TPL, len(text) / 1e3, text.count("data:image/webp")))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--extract":
        extract(sys.argv[2])
    elif len(sys.argv) == 1:
        build()
    else:
        print(__doc__)
        sys.exit(2)
