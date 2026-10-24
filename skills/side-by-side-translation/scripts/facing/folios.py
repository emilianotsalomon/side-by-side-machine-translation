"""Folios and printer's signatures against book.json: p.rh text = folio.format with the printed page number
(none on folio.none scans); p.<class> marks as listed in "marks".  Translators "correct" misprinted folios and
write scan numbers — this catches both.  usage: folios.py WORK [first last]   (silent = fine)"""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W = sys.argv[1]
cfg = book.load(W)
a, b = (int(sys.argv[2].lstrip('s')), int(sys.argv[3].lstrip('s'))) if len(sys.argv) > 3 else (cfg['first'], cfg['last'])
classes = sorted({m['class'] for m in cfg['marks']})
for ps in book.pages(cfg, a, b):
    p = int(ps[1:])
    f = f'{W}/en/{ps}.html'
    if not os.path.exists(f):
        print(ps, 'MISSING'); continue
    s = open(f).read()
    exp = book.expected_folio(cfg, p)
    m = re.search(r'<p class="rh[^"]*"[^>]*>(.*?)</p>', s, re.S)
    got = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).strip() if m else None
    if exp is None and got:
        print(ps, f'folio {got!r} but none is printed here')
    elif exp is not None and got is None:
        print(ps, f'no folio (expected {exp!r})')
    elif exp is not None and exp.replace(' ', '') not in got.replace(' ', ''):
        print(ps, f'folio {got!r}, expected {exp!r} (check the scan: keep a genuine misprint)')
    want = book.expected_marks(cfg, p)
    for c in classes:
        have = [re.sub(r'<[^>]+>', ' ', x).split()[-1] if re.sub(r'<[^>]+>', ' ', x).split() else ''
                for x in re.findall(rf'<p class="{c}"[^>]*>(.*?)</p>', s, re.S)]
        w = [t for cc, t in want if cc == c]
        if have != w:
            print(ps, f'{c}: {have} expected {w}')
