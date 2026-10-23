#!/usr/bin/env python3
"""Inject the current index.json into the page template and write the final HTML.

Recipe cards are pre-rendered as static HTML so the list is visible even in
viewers that block JavaScript (e.g. WhatsApp's document preview). When JS runs,
the app re-renders dynamically as usual.
"""
import json, os
import html as htmllib

HOME = os.path.expanduser("~")
TPL = os.path.join(HOME, "workspace/recipe-finder/page_template.html")
IDX = os.path.join(HOME, "workspace/recipe-finder/data/index.json")
THUMBS = os.path.join(HOME, "workspace/recipe-finder/data/thumbs.json")
OUT = os.path.join(HOME, "workspace/your_files/recipe-finder.html")
PLACEHOLDER = "/*__INDEX_JSON__*/null"


def card_html(r):
    # NOTE: no <img> here on purpose. WhatsApp-style viewers block remote
    # images (showing broken icons) and can't run the onerror fallback, so the
    # static version stays text-only. Browsers with JS get images via card().
    p = ['<article class="card">']
    p.append("<h3>%s</h3>" % htmllib.escape(r["title"]))
    p.append('<div class="meta"><span class="badge">%s</span><span>@%s</span></div>' %
             (htmllib.escape(r["category"]), htmllib.escape(r["author"])))
    bits = []
    if r["meals"]:
        bits.append(", ".join(r["meals"]))
    if r["tags"]:
        bits.append(" ".join("#" + t for t in r["tags"]))
    if bits:
        p.append('<div class="tagline">%s</div>' % htmllib.escape(" · ".join(bits)))
    if r.get("recipe_in_comments"):
        p.append('<div class="cnote">Full recipe in the post&apos;s comments</div>')
    p.append('<a class="goto" href="%s" target="_blank" rel="noopener">View recipe on Instagram \u2192</a>' %
             htmllib.escape(r["link"], quote=True))
    p.append("</article>")
    return "".join(p)


tpl = open(TPL).read()
assert PLACEHOLDER in tpl, "placeholder missing in template"
idx = json.load(open(IDX))
try:
    thumbs = json.load(open(THUMBS))
except Exception:
    thumbs = {}
for r in idx["recipes"]:
    t = thumbs.get(r["id"])
    if t:
        r["thumb"] = t["url"]
data = json.dumps(idx)
html = tpl.replace(PLACEHOLDER, data)
# static pre-render for no-JS viewers
cards = "".join(card_html(r) for r in idx["recipes"])
assert '<div id="results"></div>' in html
html = html.replace('<div id="results"></div>', '<div id="results">%s</div>' % cards)
html = html.replace('<p id="sub">Loading\u2026</p>',
                    '<p id="sub">%s saved recipes \u00b7 tap ingredients to search</p>'
                    % f"{idx['meta']['total']:,}")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w").write(html)
print(f"wrote {OUT} ({len(html)//1024}KB, {len(idx['recipes'])} static cards)")
