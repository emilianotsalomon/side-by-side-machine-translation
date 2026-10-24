"""Per-page sanity checks: anchors monotonic and within the page, balanced tags, EN/DE length ratio (an omission
or a wrong page split shows up here).  usage: check.py WORK [first last]   (sNNN or NNN; silent = fine)"""
import sys, re, json, os, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W = sys.argv[1]
cfg = book.load(W)
a, b = (int(sys.argv[2].lstrip('s')), int(sys.argv[3].lstrip('s'))) if len(sys.argv) > 3 else (cfg['first'], cfg['last'])
lo, hi = cfg.get('ratio', [0.75, 1.35])
for ps in book.pages(cfg, a, b):
    f = f'{W}/en/{ps}.html'
    if not os.path.exists(f):
        continue
    s = open(f).read()
    L = json.load(open(f'{W}/lines/{ps}.json'))['lines']
    probs = []
    ls = [float(x) for x in re.findall(r'data-l="(-?[\d.]+)"', s)]
    if any(y < x for x, y in zip(ls, ls[1:])):
        probs.append(f'anchors not monotonic {ls}')
    if ls and ls[-1] > len(L) + 4:
        probs.append(f'anchor {ls[-1]} > {len(L)} lines')
    for t in ('p', 'em', 'span', 'sup', 'h1', 'h2', 'h3', 'h4', 'div', 'i', 'b'):
        if len(re.findall(f'<{t}[ >]', s)) != len(re.findall(f'</{t}>', s)):
            probs.append(f'unbalanced <{t}>')
    if re.search(r'&(?![a-z]+;|#\d+;)', s):
        probs.append('unescaped &')
    en = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<p class="rh.*?</p>', '', s, flags=re.S)))
    tsv, txt = f'{W}/ocr/{ps}.tsv', f'{W}/ocr/{ps}.txt'
    de = (' '.join(r.split('\t', 4)[4] for r in open(tsv).read().splitlines() if r) if os.path.exists(tsv)
          else open(txt).read() if os.path.exists(txt) else '')
    ne, nd = len(re.sub(r'\s+', '', en)), len(re.sub(r'\s+', '', de))
    if nd > 300 and not lo <= ne / nd <= hi:
        probs.append(f'length ratio {ne / nd:.2f}')
    if probs:
        print(ps, '; '.join(probs))
