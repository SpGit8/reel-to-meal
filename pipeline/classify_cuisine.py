#!/usr/bin/env python3
"""Cuisine classification pass for the Recipe Finder index.

Judges ONE cuisine label per recipe from title + detected ingredients +
caption/extract text. Signal-scoring: dish names and distinctive ingredients
score per cuisine; a label is assigned only when the top score clears a
threshold and beats the runner-up (or wins via a title signal). Anything
weak, generic or genuinely tied stays Unclassified (None).

Labels are judged/inferred, never facts. Output: data/cuisine_judged.json
{recipe_id: "Cuisine" | null} covering every recipe in the index.
Convention: EVERY id is present; null = Unclassified.
"""
import json, re, sys
from collections import Counter, defaultdict

BASE = '/home/hatch/workspace/recipe-finder'

# signal: (regex, title_points, body_points). Title dish names weigh most.
SIGNALS = {
'Indian': [
    (r'\bdosa\b',5,2),(r'\bidli\b',5,2),(r'\buttapam\b',5,2),(r'\bappam\b',5,2),
    (r'\bpongal\b',5,2),(r'\bupma\b',5,2),(r'\bpoha\b',4,2),(r'\bthepla',5,2),
    (r'\bparatha',5,2),(r'\bparotta',5,2),(r'\bbhatura',5,2),(r'\bchapati',5,2),
    (r'\bphulka',5,2),(r'\bkhakhra',5,2),(r'\bhandvo\b',5,2),(r'\bdhokla',5,2),
    (r'\bkhandvi',5,2),(r'\bmuthia',5,2),(r'\bundhiyu',5,2),(r'\bsambar\b',5,2),
    (r'\brasam\b',5,2),(r'\bporiyal\b',5,2),(r'\bkootu\b',5,2),(r'\bavial\b',5,2),
    (r'\bthoran\b',5,2),(r'\bpachadi\b',5,2),(r'\bkadhi\b',5,2),(r'\bkhichdi',5,2),
    (r'\bkhichri',5,2),(r'\bpulao\b',5,2),(r'\bbiryani\b',5,2),(r'\bbiriyani\b',5,2),
    (r'\btehri\b',5,2),(r'\bchutney',3,1),(r'\braita\b',5,2),(r'\bbharta\b',5,2),
    (r'\bmasala\b',3,2),(r'\btadka\b',5,2),(r'\btikka\b',5,2),(r'\btandoori',5,2),
    (r'\bchole\b',5,2),(r'\brajma\b',5,2),(r'\blobiya\b',5,2),(r'\bghugni\b',5,2),
    (r'\busal\b',5,2),(r'\bmisal\b',5,2),(r'\bpav bhaji\b',5,2),(r'\bvada pav\b',5,2),
    (r'\bbhel\b',5,2),(r'\bchaat\b',5,2),(r'\bsamosa',5,2),(r'\bpakora',5,2),
    (r'\bpakoda',5,2),(r'\bkachori',5,2),(r'\bgalouti',5,2),(r'\bseekh\b',3,1),
    (r'\bkofta',3,1),(r'\bkeema\b',5,2),(r'\bkheema\b',5,2),(r'\bhaleem\b',5,2),
    (r'\bnihari\b',5,2),(r'\bkorma\b',3,1),(r'\bvindaloo',5,2),(r'\bchettinad',5,2),
    (r'\bxacuti',5,2),(r'\bcafreal',5,2),(r'\brogan josh',5,2),(r'\bmakhani',5,2),
    (r'\blababdar',5,2),(r'\bdo pyaza',5,2),(r'\bachari\b',5,2),(r'\bpaneer',5,3),
    (r'\bsabzi\b',5,2),(r'\bsabji\b',5,2),(r'\bshaak\b',5,2),(r'\bvaran\b',5,2),
    (r'\bamti\b',5,2),(r'\bpithla',5,2),(r'\bzunka',5,2),(r'\bsolkadhi',5,2),
    (r'\bkokum\b',5,2),(r'\bmodak\b',5,2),(r'\bladoo',5,2),(r'\bladdu',5,2),
    (r'\bbarfi\b',5,2),(r'\bburfi\b',5,2),(r'\bhalwa\b',3,1),(r'\bkheer\b',5,2),
    (r'\bpayasam\b',5,2),(r'\bshrikhand',5,2),(r'\bbasundi',5,2),(r'\brabri\b',5,2),
    (r'\bjalebi',5,2),(r'\bgulab jamun',5,2),(r'\brasmalai',5,2),(r'\bras malai',5,2),
    (r'\bsandesh\b',5,2),(r'\bkesari\b',5,2),(r'\bsheera\b',5,2),(r'\bthandai',5,2),
    (r'\blassi\b',5,2),(r'\bchaas\b',5,2),(r'\bjaljeera',5,2),(r'\baam panna',5,2),
    (r'\bfalooda',3,1),(r'\bkulfi',5,2),(r'\bshikanji',5,2),(r'\bsattu\b',5,2),
    (r'\blitti\b',5,2),(r'\bchokha',5,2),(r'\bbaati\b',5,2),(r'\bchurma',5,2),
    (r'\bgatte\b',5,2),(r'\bvadam\b',5,2),(r'\bpesarattu',5,2),(r'\bpaniyaram',5,2),
    (r'\bidiyappam',5,2),(r'\bputtu\b',5,2),(r'\bolan\b',5,2),(r'\berissery',5,2),
    (r'\bbisi bele',5,2),(r'\bbisibelebath',5,2),(r'\bpuliyodharai',5,2),
    (r'\bpulihora',5,2),(r'\bcurd rice',5,2),(r'\blemon rice',4,2),
    (r'\btamarind rice',5,2),(r'\bakki rotti',5,2),(r'\bneer dosa',5,2),
    (r'\bghee roast',5,2),(r'\bkuzhambu',5,2),(r'\bvaruval',5,2),
    (r'\bindian\b',4,2),(r'\bpunjabi\b',4,2),(r'\bgujarati\b',4,2),
    (r'\bmarathi\b',4,2),(r'\bmaharashtrian',4,2),(r'\bbengali\b',4,2),
    (r'\bkerala\b',4,2),(r'\btamil\b',4,2),(r'\btelugu\b',4,2),(r'\bandhra\b',4,2),
    (r'\bhyderabadi',4,2),(r'\bawadhi',4,2),(r'\blucknowi',4,2),(r'\bkashmiri\b',4,2),
    (r'\brajasthani',4,2),(r'\bmangalorean',4,2),(r'\bgoan\b',4,2),(r'\bkonkani',4,2),
    (r'\bsindhi\b',4,2),(r'\bodia\b',4,2),(r'\bassamese',4,2),(r'\bdhaba\b',4,2),
    (r'\btiffin\b',3,1),(r'\bmumbai\b',2,1),(r'\bdelhi\b',2,1),
    (r'\bgaram masala\b',0,3),(r'\bchaat masala\b',0,3),(r'\bkasuri methi\b',0,3),
    (r'\basafoetida\b',0,3),(r'\bhing\b',0,2),(r'\bcurry leaves\b',0,2),
    (r'\burad dal\b',0,2),(r'\bchana dal\b',0,2),(r'\btoor dal\b',0,2),
    (r'\bmasoor dal\b',0,2),(r'\bbesan\b',0,2),(r'\bamchur\b',0,3),
    (r'\bajwain\b',0,2),(r'\bkalonji\b',0,2),(r'\bsabudana\b',0,2),
    (r'\bdal\b',2,1),(r'\bdahl\b',3,1),(r'\bcurry\b',2,1),
    (r'\broti\b',2,1),(r'\bnaan\b',2,1),(r'\bpapad',3,1),
],
'Italian': [
    (r'\bspaghetti',5,2),(r'\bpenne\b',5,2),(r'\bfusilli',5,2),(r'\brigatoni',5,2),
    (r'\bfettuccine',5,2),(r'\blinguine',5,2),(r'\blasagna',5,2),(r'\blasagne',5,2),
    (r'\brisotto',5,2),(r'\bgnocchi',5,2),(r'\barrabbiata',5,2),(r'\baglio e olio',5,2),
    (r'\bputtanesca',5,2),(r'\bcarbonara',5,2),(r'\bcacio e pepe',5,2),
    (r'\bpesto\b',4,2),(r'\bmarinara',4,1),(r'\balfredo',4,1),(r'\bbolognese',5,2),
    (r'\bparmigiana',5,2),(r'\bbruschetta',4,1),(r'\bcrostini',3,1),(r'\bfocaccia',5,2),
    (r'\bciabatta',4,1),(r'\bpizza\b',4,1),(r'\btiramisu',5,2),(r'\bpanna cotta',5,2),
    (r'\bcannoli',5,2),(r'\bbiscotti',4,1),(r'\bpolenta',4,1),(r'\bminestrone',5,2),
    (r'\bcaprese',5,2),(r'\borzo\b',3,1),(r'\bpasta\b',3,1),
    (r'\bitalian\b',4,2),(r'\bparmigiano',0,2),(r'\bparmesan',0,1),
    (r'\bmascarpone',0,2),(r'\bburrata',0,1),(r'\bprosciutto',0,2),(r'\bpancetta',0,2),
],
'Mexican': [
    (r'\btaco',5,2),(r'\bburrito',5,2),(r'\bquesadilla',5,2),(r'\benchilada',5,2),
    (r'\bfajita',5,2),(r'\bnachos\b',5,2),(r'\bguacamole',5,2),(r'\bpico de gallo',5,2),
    (r'\belote\b',5,2),(r'\besquites',5,2),(r'\bchilaquiles',5,2),
    (r'\bhuevos rancheros',5,2),(r'\btamale',5,2),(r'\bpozole',5,2),
    (r'\bcarnitas',5,2),(r'\bal pastor',5,2),(r'\bbirria',5,2),(r'\bchipotle',4,2),
    (r'\btomatillo',5,2),(r'\bsalsa verde',4,1),(r'\bsalsa roja',4,1),
    (r'\bchurro',3,1),(r'\bhorchata',3,1),(r'\bagua fresca',5,2),
    (r'\bmexican\b',4,2),(r'\bcotija',0,2),(r'\btaj[ií]n',0,2),(r'\bqueso\b',3,1),
    (r'\bsalsa\b',1,1),
],
'Japanese': [
    (r'\bmiso\b',4,2),(r'\bsushi\b',5,2),(r'\bsashimi',5,2),(r'\bramen\b',5,2),
    (r'\budon\b',5,2),(r'\bsoba\b',5,2),(r'\byakitori',5,2),(r'\bteriyaki',5,2),
    (r'\btempura',5,2),(r'\bkatsu\b',5,2),(r'\bkaraage',5,2),(r'\bgyoza',4,2),
    (r'\btakoyaki',5,2),(r'\bokonomiyaki',5,2),(r'\bonigiri',5,2),(r'\bomurice',5,2),
    (r'\bdonburi',5,2),(r'\boyakodon',5,2),(r'\bmatcha',4,1),(r'\bmochi\b',4,1),
    (r'\bedamame',3,1),(r'\bjapanese\b',4,2),(r'\bjapanese curry',5,2),
    (r'\bkorokke',5,2),(r'\bchawanmushi',5,2),(r'\bsukiyaki',5,2),(r'\bshabu',4,1),
    (r'\bdengaku',5,2),(r'\bagedashi',5,2),(r'\bdashi\b',0,2),(r'\bmirin\b',0,2),
    (r'\bnori\b',0,1),(r'\byuzu\b',0,2),(r'\bfurikake',0,3),(r'\bkewpie',0,2),
    (r'\bponzu',0,2),(r'\bshichimi',0,2),
],
'Korean': [
    (r'\bkimchi',5,2),(r'\bgochujang',5,3),(r'\bgochugaru',5,3),(r'\bbulgogi',5,2),
    (r'\bbibimbap',5,2),(r'\bjapchae',5,2),(r'\btteokbokki',5,2),(r'\bkimbap',5,2),
    (r'\bgimbap',5,2),(r'\bdoenjang',5,2),(r'\bssamjang',5,2),(r'\bdakgalbi',5,2),
    (r'\bjook\b',4,1),(r'\bjuk\b',4,1),(r'\btteok\b',4,1),(r'\bhotteok',5,2),
    (r'\bpajeon',5,2),(r'\bsundubu',5,2),(r'\bjjigae',5,2),(r'\bgalbi',5,2),
    (r'\byangnyeom',5,2),(r'\bkorean\b',4,2),(r'\bdubu\b',3,1),(r'\bbanchan',5,2),
],
'Thai': [
    (r'\bpad thai',5,2),(r'\btom yum',5,2),(r'\btom kha',5,2),(r'\bthai\b',4,2),
    (r'\bmango sticky rice',5,2),(r'\bsom tam',5,2),(r'\blarb\b',5,2),
    (r'\bpad see ew',5,2),(r'\bpad kra pao',5,2),(r'\bpad kaprao',5,2),
    (r'\bmassaman',5,2),(r'\bpanang',5,2),(r'\bthai basil',0,3),
    (r'\blemongrass',0,2),(r'\bgalangal',0,3),(r'\bkaffir lime',0,3),
],
'Chinese': [
    (r'\bdim sum',5,2),(r'\bhar gow',5,2),(r'\bxiao long bao',5,2),(r'\bbaozi',5,2),
    (r'\bcongee',4,1),(r'\bchow mein',5,2),(r'\blo mein',5,2),(r'\bhakka',5,2),
    (r'\bmanchurian',5,2),(r'\bschezwan',5,2),(r'\bkung pao',5,2),(r'\bmapo',5,2),
    (r'\bdan dan',5,2),(r'\bmala\b',4,2),(r'\bsichuan',5,2),(r'\bszechuan',5,2),
    (r'\bhunan\b',5,2),(r'\bcantonese',5,2),(r'\bchar siu',5,2),(r'\bbok choy',4,2),
    (r'\bwonton',4,1),(r'\bhot pot',4,1),(r'\blap cheong',5,2),
    (r'\bchinese\b',4,2),(r'\bscallion pancake',4,1),(r'\bcentury egg',5,2),
    (r'\bhoisin',0,2),(r'\boyster sauce',0,2),(r'\bshaoxing',0,3),
    (r'\bdoubanjiang',0,3),(r'\bfive spice',0,2),(r'\bchilli oil',2,1),
    (r'\bchili oil',2,1),
],
'Vietnamese': [
    (r'\bpho\b',5,2),(r'\bbanh mi',5,2),(r'\bbun cha',5,2),(r'\bgoi cuon',5,2),
    (r'\bvietnamese\b',4,2),(r'\bbanh xeo',5,2),(r'\bcha gio',5,2),(r'\bnuoc cham',0,3),
],
'Indonesian': [
    (r'\bnasi goreng',5,2),(r'\bmie goreng',5,2),(r'\brendang',5,2),
    (r'\bgado gado',5,2),(r'\bsoto ayam',5,2),(r'\bbakso',5,2),
    (r'\bindonesian\b',4,2),(r'\bbalinese',4,2),(r'\bkecap manis',0,3),
    (r'\bsatay',3,1),(r'\bsambal',3,1),
],
'Malaysian': [
    (r'\bnasi lemak',5,2),(r'\blaksa',5,2),(r'\bchar kway teow',5,2),
    (r'\broti canai',4,2),(r'\bmalaysian\b',4,2),(r'\bsatay',3,1),(r'\bsambal',3,1),
],
'Middle Eastern': [
    (r'\bshawarma',5,2),(r'\bfalafel',5,2),(r'\bhummus',4,2),(r'\bshakshuka',5,2),
    (r"\bza'atar",5,2),(r'\bzaatar',5,2),(r'\bmuhammara',5,2),(r'\bbaba ganoush',5,2),
    (r'\btabbouleh',5,2),(r'\bfattoush',5,2),(r'\bkibbeh',5,2),(r'\blabneh',4,2),
    (r'\bhalloumi',3,1),(r'\bkunafa',5,2),(r'\bknafeh',5,2),(r'\bbaklava',4,1),
    (r'\bshish tawook',5,2),(r'\btoum\b',5,2),(r'\bdukkah',4,2),(r'\bful medames',5,2),
    (r'\bmsakhan',5,2),(r'\bmaqluba',5,2),(r'\blebanese\b',4,2),
    (r'\bmiddle eastern',4,2),(r'\bmenemen',4,2),(r'\bpide\b',4,2),
    (r'\blahmancun|lahmacun',4,2),(r'\bg[öo]zleme',4,2),(r'\bb[öo]rek',4,1),
    (r'\bturkish\b',4,2),(r'\bpersian\b',4,2),(r'\btahdig',5,2),(r'\bghormeh',5,2),
    (r'\bfesenjan',5,2),(r'\bmoroccan\b',4,2),(r'\bharissa',3,1),(r'\bsumac',0,2),
    (r'\btahini',0,1),(r'\bpita\b',1,1),
],
'Greek': [
    (r'\bspanakopita',5,2),(r'\bmoussaka',5,2),(r'\bsouvlaki',5,2),(r'\bgyro',4,1),
    (r'\btzatziki',5,2),(r'\bgreek salad',5,2),(r'\bdolmades',4,1),(r'\bdolma\b',3,1),
    (r'\bavgolemono',5,2),(r'\bspanakorizo',5,2),(r'\bgigantes',5,2),
    (r'\bgreek\b',4,2),(r'\bfeta\b',0,1),
],
'Mediterranean': [
    (r'\bmediterranean\b',4,2),
],
'American': [
    (r'\bsmash burger',5,2),(r'\bburger',4,1),(r'\bmac and cheese',5,2),
    (r'\bmac n cheese',5,2),(r'\bmac & cheese',5,2),(r'\bbuffalo\b',4,1),
    (r'\bpulled pork',5,2),(r'\bcornbread',5,2),(r'\bsmores\b',5,2),
    (r"\bs'mores",5,2),(r'\bkey lime pie',5,2),(r'\bpecan pie',5,2),
    (r'\bpumpkin pie',4,1),(r'\bcobbler',4,1),(r'\bsloppy joe',5,2),
    (r'\bclam chowder',5,2),(r'\blobster roll',5,2),(r'\bjambalaya',5,2),
    (r'\bgumbo\b',5,2),(r'\bcajun',4,2),(r'\bblt\b',4,1),(r'\bamerican\b',4,2),
],
'French': [
    (r'\bcroissant',5,2),(r'\bquiche',5,2),(r'\bratatouille',5,2),
    (r'\bbouillabaisse',5,2),(r'\bcoq au vin',5,2),(r'\bbourguignon',5,2),
    (r'\bsouffl[eé]',4,1),(r'\bcr[eè]me br[uû]l[eé]e',5,2),(r'\bmadeleine',4,1),
    (r'\bbrioche',3,1),(r'\bni[çc]oise',5,2),(r'\bfrench\b',4,2),
    (r'\bgalette',4,1),(r'\bgratin',3,1),(r'\bcrepe',3,1),(r'\bcr[eê]pe',3,1),
],
'Spanish': [
    (r'\bpaella',5,2),(r'\bpatatas bravas',5,2),(r'\bgazpacho',5,2),
    (r'\bgambas',4,1),(r'\bspanish\b',4,2),(r'\bromesco',0,2),(r'\bmanchego',0,2),
],
'Sri Lankan': [
    (r'\bsri lankan',5,2),(r'\bkottu',5,2),(r'\bpol roti',5,2),
    (r'\bseeni sambol',5,2),(r'\bpol sambol',5,2),(r'\blunu miris',5,2),
    (r'\bkiribath',5,2),(r'\bwattalappam',5,2),(r'\blamprais',5,2),
    (r'\bstring hoppers',4,1),(r'\bhoppers\b',4,1),
],
'Nepali': [
    (r'\bnepali\b',5,2),(r'\bnepalese\b',5,2),(r'\bmomos\b',4,1),(r'\bmomo\b',4,1),
    (r'\bthukpa',5,2),(r'\bdal bhat',4,1),(r'\bsel roti',5,2),(r'\bchoila',5,2),
    (r'\byomari',5,2),(r'\bgundruk',5,2),
],
'Filipino': [
    (r'\bfilipino\b',4,2),(r'\badobo\b',4,1),(r'\bsisig',5,2),(r'\blumpia',5,2),
    (r'\bpancit',5,2),(r'\bsinigang',5,2),(r'\bhalo[- ]halo',5,2),
    (r'\bube\b',3,1),(r'\bkare kare',5,2),(r'\bsilog',4,1),
],
'Ethiopian': [
    (r'\bethiopian\b',5,2),(r'\binjera',5,2),(r'\bberbere',0,3),(r'\btibs\b',4,1),
],
'Caribbean': [
    (r'\bjamaican\b',4,2),(r'\bjerk\b',5,2),(r'\bcaribbean\b',4,2),
    (r'\bcallaloo',5,2),(r'\backee',5,2),(r'\brice and peas',4,1),
],
'British': [
    (r"\bshepherd'?s pie",5,2),(r'\bcottage pie',5,2),(r'\bfish and chips',5,2),
    (r'\bsticky toffee',5,2),(r'\beton mess',5,2),(r'\byorkshire pudding',5,2),
    (r'\bbritish\b',4,2),(r'\bscones\b',3,1),
],
'Peruvian': [
    (r'\bceviche',5,2),(r'\bperuvian\b',4,2),(r'\blomo saltado',5,2),
],
}

# Hand overrides from manual review: {recipe_id: label or None}
OVERRIDES = {}

INDIAN_WEAK = ['turmeric','cumin','coriander powder','ghee','mustard seeds',
               'fenugreek','coconut milk','tamarind','jaggery']
INDO_CHINESE_MARKERS = ('hakka','manchurian','schezwan')

def score_recipe(r):
    title = (r.get('title') or '').lower()
    body = ' '.join([
        (r.get('text') or '')[:2500],
        (r.get('recipe_ingredients') or ''),
        ' '.join(r.get('ingredients') or []),
    ]).lower()
    scores, title_hit = {}, {}
    for cuisine, sigs in SIGNALS.items():
        s, th = 0, False
        for pat, tp, bp in sigs:
            if re.search(pat, title):
                s += tp; th = True
            elif bp and re.search(pat, body):
                s += bp
        scores[cuisine] = s; title_hit[cuisine] = th
    # 'greek yogurt' alone is not Greek food
    if scores['Greek'] and not re.search(
            r'spanakopita|moussaka|souvlaki|gyro|tzatziki|greek salad|dolm|avgolemono|spanakorizo|gigantes', title + ' ' + body):
        if re.search(r'\bgreek\b', title + ' ' + body) and 'greek yogurt' in (title + ' ' + body):
            scores['Greek'] = 0; title_hit['Greek'] = False
    # generic curry is Indian unless clearly Thai/Japanese
    if re.search(r'\bcurry\b', title) and scores['Thai'] < 5 and scores['Japanese'] < 5:
        scores['Indian'] += 2
    # category nudges
    if r.get('category') == 'Curries':
        if scores['Thai'] < 5 and scores['Japanese'] < 5:
            scores['Indian'] += 2
    if r.get('category') == 'Lentils, Beans & Chickpeas':
        scores['Indian'] += 1
    # combo of weak Indian pantry markers
    weak = sum(1 for w in INDIAN_WEAK if w in body)
    if weak >= 3:
        scores['Indian'] += 3
    return scores, title_hit, title

def classify(r):
    scores, title_hit, _ = score_recipe(r)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (best, bs), (second, ss) = ranked[0], ranked[1]
    if bs < 5:
        return None, scores, 'below-threshold'
    if ss >= 5 and (bs - ss) <= 2 and not (title_hit[best] and not title_hit[second]):
        return None, scores, f'ambiguous:{best}({bs}) vs {second}({ss})'
    return best, scores, 'ok'

def main():
    idx = json.load(open(f'{BASE}/data/index.json'))
    recipes = idx['recipes']
    results, reasons = {}, Counter()
    borderline, lowconf = [], []
    for r in recipes:
        label, scores, why = classify(r)
        if r['id'] in OVERRIDES:
            label, why = OVERRIDES[r['id']], 'override'
        results[r['id']] = label
        reasons[why if why in ('ok','override','below-threshold') else 'ambiguous'] += 1
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if why.startswith('ambiguous'):
            borderline.append((r['id'], r['title'], why))
        if label and ranked[0][1] < 8:
            lowconf.append((r['id'], r['title'], label, ranked[0][1], ranked[1]))
    json.dump(results, open(f'{BASE}/data/cuisine_judged.json','w'),
              ensure_ascii=False, indent=1)
    counts = Counter(v for v in results.values() if v)
    print(f"total {len(results)}  classified {sum(counts.values())}  "
          f"unclassified {len(results)-sum(counts.values())}")
    print('reasons:', dict(reasons))
    print('\ncounts (desc):')
    by_id = {r['id']: r for r in recipes}
    for c, n in counts.most_common():
        print(f'  {c}: {n}')
    print('\nexamples:')
    for c, n in counts.most_common():
        ex = [by_id[i]['title'] for i, v in results.items() if v == c][:5]
        print(f'  {c}: ' + ' | '.join(ex))
    if '--dump' in sys.argv:
        dump = {'borderline': borderline, 'lowconf': lowconf,
                'unclassified': [(r['id'], r['title'], r['category'])
                                 for r in recipes if not results[r['id']]]}
        json.dump(dump, open('/tmp/cuisine_review.json','w'), ensure_ascii=False, indent=1)
        print(f"\nreview dump: {len(borderline)} borderline, {len(lowconf)} low-confidence, "
              f"{len(dump['unclassified'])} unclassified -> /tmp/cuisine_review.json")

if __name__ == '__main__':
    main()
