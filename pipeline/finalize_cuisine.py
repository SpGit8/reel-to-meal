#!/usr/bin/env python3
"""Finalize: apply hand-decided overrides (inspected items) to pass-2 output."""
import json, random
from collections import Counter

BASE = '/home/hatch/workspace/recipe-finder'
res = json.load(open(f'{BASE}/data/cuisine_judged.json'))
idx = json.load(open(f'{BASE}/data/index.json'))
by_title = {}
for r in idx['recipes']:
    by_title.setdefault(r['title'], []).append(r['id'])

FINAL_OVERRIDES = {
    # non-recipe posts that picked up a label from a cuisine word
    'Chinese Grocery Haul': None, 'Korean Pantry Staples': None,
    'CurryHub Ghost Kitchen': None, 'Daily Meal Plan': None,
    '50+ Baby Puree Ideas': None, 'Kid Snack Brands': None,
    'Vegetable Variety Tips': None,
    # miso used as a mere condiment in Western-format dishes
    'Peanut-Miso Chickpea Salad': None, 'Miso Tahini Peas on Sourdough': None,
    'Mushroom Miso Sandwich': None,
    # genuine fusions with no dominant cuisine
    'French Onion Pasta': None, 'Mexican Black Bean Pasta': None,
    'Coconut Jaggery Rice Paper Rolls': None,
    'Rice Paper Almond Croissant': None, 'Chilli Oil Rice Paper Noodles': None,
    'Fried French Toast': None,
    # inspected corrections
    'Buldak Spicy Chicken Ramen': 'Korean',
    'Golden Spaghettios': 'American',
    'Cheesy Cauliflower Macaroni': 'American',
    'Broccoli Cheddar Soup': 'American',
    'Aloo Pizza Bites': 'Indian',
    'Chicken Fried Rice': 'Indian',
    'Spicy Peanut Chilli Oil Maggi': 'Indian',
    'Satay Noodle Soup': 'Malaysian',
    'Turkish Pasta': 'Middle Eastern',
    'Miso Mushroom Congee': 'Chinese',
    'Creamy Chilli Oil Ramen': 'Japanese',
    'Vegan Bún Bò Huế': 'Vietnamese',
    'Ema Datshi Pasta': 'Bhutanese',
    'Feta Chili Oil Breakfast Tacos': 'Mexican',
    'Sweet Chilli Cajun Chicken Tacos': 'Mexican',
}
applied = []
for title, label in FINAL_OVERRIDES.items():
    for rid in by_title.get(title, []):
        res[rid] = label; applied.append((title, label))
print('overrides applied:', len(applied))
json.dump(res, open(f'{BASE}/data/cuisine_judged.json', 'w'),
          ensure_ascii=False, indent=1)

counts = Counter(v for v in res.values() if v)
by_id = {r['id']: r for r in idx['recipes']}
print(f"\nFINAL: total {len(res)}  classified {sum(counts.values())}  "
      f"unclassified {len(res) - sum(counts.values())}")
for c, n in counts.most_common():
    ex = [by_id[i]['title'] for i, v in res.items() if v == c][:5]
    print(f'  {c}: {n}  :: ' + ' | '.join(ex))
random.seed(123)
print('\nspot-check samples:')
for c in counts:
    titles = [by_id[i]['title'] for i, v in res.items() if v == c]
    for t in random.sample(titles, min(5, len(titles))):
        print(f'  {c} | {t}')
