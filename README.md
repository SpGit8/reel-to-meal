# Reel to Meal
A tool to help find recipes, plan out and generate weekly meals, generate a grocery list, share them and many more.

## How this works

This repo is the source project for the Reel to Meal page (formerly the
Recipe Finder) served on GitHub Pages.

- `data/` — the recipe data: the index of saved recipes, verbatim recipe
  extracts, parsed quantities, prep hints, and judged labels (meals,
  categories, cuisines).
- `pipeline/` — the Python pipeline that produces that data: it pulls
  the owner's new Instagram saves, rebuilds the index, extracts recipes,
  and judges labels.
- `page/template.html` — the page's design and code, with placeholders
  where the data goes.
- `assets/thumbs/` — the full-size recipe photos; the page starts from
  small built-in copies and upgrades to these.
- `build_page.py` — regenerates `index.html` from the template + data,
  including the static pre-rendered cards and their WebP thumbnails.
- `index.html` — the built page (also rebuilt fresh by the Action).

The data refresh itself runs on Juno's side — it needs the owner's
Instagram session, which never goes to GitHub. A refresh lands here as a
commit touching `data/` (and sometimes `page/`), and that commit
triggers the GitHub Action in `.github/workflows/build.yml`, which
rebuilds the page and deploys it to Pages. (Pages' source must be set
to "GitHub Actions" in the repo settings.)

To build locally: `pip install pillow && python3 build_page.py`.
To refresh the page design after the hosted page changes, run
`python3 build_page.py --extract <fresh-export.html>` and commit the
updated `page/template.html` together with the data.

