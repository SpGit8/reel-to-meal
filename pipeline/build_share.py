#!/usr/bin/env python3
"""Build the share-friendly Recipe Finder page.

Thumbnails are downloaded, downscaled and embedded as base64 data URIs in the
static card pre-render, so images display even in viewers that block remote
content and JavaScript (e.g. WhatsApp's document preview).

Output: ~/workspace/your_files/recipe-finder-share.html
Cache:  ~/workspace/recipe-finder/data/share_thumbs.json (resumable)
"""
import json, os, io, base64, urllib.request
import html as htmllib
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
THUMBS = os.path.join(HOME, "workspace/recipe-finder/data/thumbs.json")
CACHE = os.path.join(HOME, "workspace/recipe-finder/data/share_thumbs.json")
IDX = os.path.join(HOME, "workspace/recipe-finder/data/index.json")
TPL = os.path.join(HOME, "workspace/recipe-finder/page_template.html")
OUT = os.path.join(HOME, "workspace/your_files/recipe-finder-share.html")
PLACEHOLDER = "/*__INDEX_JSON__*/null"

from PIL import Image  # noqa: E402


def fetch_one(item):
    """Download the original bytes and embed untouched — Instagram's og:image
    previews are only ~360px wide, so any resizing just loses sharpness."""
    pid, url = item
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0",
                          "Referer": "https://www.instagram.com/"})
        raw = urllib.request.urlopen(req, timeout=30).read()
        if raw[:8] == b'\x89PNG\r\n\x1a\n':
            mime = "image/png"
        elif raw[:2] == b'\xff\xd8':
            mime = "image/jpeg"
        else:
            return pid, None
        return pid, "data:%s;base64," % mime + base64.b64encode(raw).decode()
    except Exception:
        return pid, None


def card_html(r, data_uri):
    p = ['<article class="card">']
    if data_uri:
        # data URIs need no network, so they render even in locked-down viewers
        p.append('<img class="thumb" loading="lazy" src="%s" alt="">' % data_uri)
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


def main():
    thumbs = json.load(open(THUMBS))
    try:
        cache = json.load(open(CACHE))
    except Exception:
        cache = {}
    todo = [(pid, v["url"]) for pid, v in thumbs.items() if pid not in cache]
    print(f"cached={len(cache)} to_fetch={len(todo)}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for pid, uri in ex.map(fetch_one, todo):
            if uri:
                cache[pid] = uri
            done += 1
            if done % 50 == 0:
                json.dump(cache, open(CACHE, "w"))
                print(f"progress {done}/{len(todo)} embedded={len(cache)}", flush=True)
    json.dump(cache, open(CACHE, "w"))
    print(f"images embedded: {len(cache)}", flush=True)

    idx = json.load(open(IDX))
    # remote URLs stay in the dynamic JSON for real browsers; static cards use data URIs
    for r in idx["recipes"]:
        t = thumbs.get(r["id"])
        if t:
            r["thumb"] = t["url"]

    tpl = open(TPL).read()
    assert PLACEHOLDER in tpl
    html = tpl.replace(PLACEHOLDER, json.dumps(idx))
    cards = "".join(card_html(r, cache.get(r["id"])) for r in idx["recipes"])
    assert '<div id="results"></div>' in html
    html = html.replace('<div id="results"></div>', '<div id="results">%s</div>' % cards)
    html = html.replace('<p id="sub">Loading\u2026</p>',
                        '<p id="sub">%s saved recipes \u00b7 tap ingredients to search</p>'
                        % f"{idx['meta']['total']:,}")
    open(OUT, "w").write(html)
    print(f"wrote {OUT} ({len(html)//1024}KB)", flush=True)


if __name__ == "__main__":
    main()
