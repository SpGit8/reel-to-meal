#!/usr/bin/env python3
"""Parse ingredient quantities for the serving scaler.

Reads data/index.json (recipes with recipe_ingredients), writes
data/quantities.json: {recipe_id: {"base": <int>, "base_stated": <bool>,
"lines": [{"raw": str} | {"raw": str, "qty": [lo, hi|null], "rest": str}]}}

Only the leading numeric token(s) of a line are treated as the quantity;
everything after is preserved verbatim in "rest". Lines that do not start
with a clean quantity stay {"raw": ...} and never scale.
Base servings: a stated yield in the caption/extract ("serves 4",
"makes 12", "yield: 6", "for 4 people") wins; otherwise 1 (owner's rule).
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')

FRAC = {'½': 0.5, '¼': 0.25, '¾': 0.75, '⅓': 1/3, '⅔': 2/3,
        '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875}
NUM = (r'(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*[½¼¾⅓⅔⅛⅜⅝⅞]?'
       r'|[½¼¾⅓⅔⅛⅜⅝⅞])')
QTY_RE = re.compile(r'^\s*(' + NUM + r')(?:\s*[-–~]\s*(' + NUM + r'))?(?=\s|$)')
SERVES_RE = re.compile(
    r'(?:serves?|serving[s]?[:\s]|makes?|yield[s]?[:\s]|for)\s*[:\-]?\s*(\d{1,2})'
    r'(?:\s*(?:people|persons|servings?|pieces|pcs|rotis?|dosas?|idlis?|parathas?|pancakes?|muffins?|cookies?|ladoos?|laddus?|burgers?|sandwiches|rolls?|bowls?|cups?|glasses))?',
    re.I)


def numval(s):
    s = s.strip()
    total = 0.0
    for part in s.split():
        if '/' in part:
            a, b = part.split('/', 1)
            total += float(a) / float(b)
        elif part and part[-1] in FRAC:
            head = part[:-1]
            total += (float(head) if head else 0.0) + FRAC[part[-1]]
        else:
            total += float(part)
    return total


def parse_line(line):
    m = QTY_RE.match(line)
    if not m:
        return {'raw': line}
    rest = line[m.end():]
    if rest.startswith('-'):        # e.g. "5-spice powder" is not a quantity
        return {'raw': line}
    try:
        lo = numval(m.group(1))
        hi = numval(m.group(2)) if m.group(2) else None
    except ValueError:
        return {'raw': line}
    if lo <= 0 or lo > 10000:
        return {'raw': line}
    return {'raw': line, 'qty': [lo, hi], 'rest': rest}


def stated_servings(recipe):
    text = ' '.join([recipe.get('caption') or '',
                     recipe.get('recipe_ingredients') or '',
                     recipe.get('recipe_method') or ''])[:4000]
    m = SERVES_RE.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 60:
            return n
    return None


def main():
    idx = json.load(open(os.path.join(DATA, 'index.json')))
    out = {}
    n_lines = n_qty = 0
    for r in idx['recipes']:
        ing = (r.get('recipe_ingredients') or '').strip()
        if not ing:
            continue
        lines = [parse_line(l) for l in ing.split('\n') if l.strip()]
        if not any('qty' in l for l in lines):
            continue
        base = stated_servings(r)
        out[r['id']] = {'base': base if base else 1,
                        'base_stated': bool(base),
                        'lines': lines}
        n_lines += len(lines)
        n_qty += sum(1 for l in lines if 'qty' in l)
    json.dump(out, open(os.path.join(DATA, 'quantities.json'), 'w'))
    print(f'recipes with a scaler: {len(out)} | lines: {n_lines} | scalable: {n_qty}')


if __name__ == '__main__':
    main()
