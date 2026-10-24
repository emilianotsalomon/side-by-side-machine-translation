"""Page joins: missing English pages and words duplicated across a page boundary (batch seams, translators'
"completed clause" overlaps).  usage: seams.py WORK [first last]   (prints 'missing: none' when complete)"""
import sys, re, os, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W = sys.argv[1]
cfg = book.load(W)
a, b = (int(sys.argv[2].lstrip('s')), int(sys.argv[3].lstrip('s'))) if len(sys.argv) > 3 else (cfg['first'], cfg['last'])
pages = book.pages(cfg, a, b)
miss = [p for p in pages if not os.path.exists(f'{W}/en/{p}.html')]
print('missing:', ' '.join(miss) or 'none')


def words(p):
    s = open(f'{W}/en/{p}.html').read()
    s = re.sub(r'<p class="(rh|sig|sigf|cw)[^"]*".*?</p>', ' ', s, flags=re.S)
    s = re.sub(r'<p class="note.*?</p>', ' ', s, flags=re.S)
    s = re.sub(r'<!--.*?-->', ' ', s)
    return html.unescape(re.sub(r'<[^>]+>', ' ', s)).split()


have = [p for p in pages if p not in miss]
for x, y in zip(have, have[1:]):
    wa, wb = words(x), words(y)
    if not wa or not wb:
        continue
    for k in (4, 3, 2):
        ta = [re.sub(r'\W', '', w).lower() for w in wa[-k:]]
        tb = [re.sub(r'\W', '', w).lower() for w in wb[:k]]
        if ta == tb and any(len(t) > 3 for t in ta):
            print(f'dup {x}|{y}: ...{" ".join(wa[-k:])} | {" ".join(wb[:k])}...'); break
    else:
        if len(wa[-1]) > 2 and re.sub(r'\W', '', wa[-1]).lower() == re.sub(r'\W', '', wb[0]).lower():
            print(f'dup1 {x}|{y}: {wa[-1]} | {wb[0]}')
