"""Assemble English page fragments into one printable HTML (English on the right half of each sheet).
usage: build.py WORK OUT.html [first last]      (scan numbers; default = the whole book)
Fragment = WORK/en/sPPP.html, a flat sequence of blocks anchored by data-l="N" (N = red line number; fractions
interpolate; < 1 / > last extrapolate by one line pitch) or data-at="Y" (scan px, blue ruler).  <p class="rh">
without data-l is placed at the printed folio.  <!-- fs=9.5 --> / <!-- lh=1.3 --> override the automatic type size
(from the German line pitch) and line height.  Geometry and fit limits come from WORK/book.json; book-specific CSS
goes in WORK/extra.css."""
import sys, os, re, json
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W, OUT = sys.argv[1], sys.argv[2]
cfg = book.load(W)
a, b = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (cfg['first'], cfg['last'])
G, F = cfg['geometry'], cfg['fit']
SC, TOP, HALF, TW = G['sc'], G['top'], G['half'], G['tw']
SW, SH = G['sheet']
HERE = os.path.dirname(os.path.abspath(__file__))
pages = [p[1:] for p in book.pages(cfg, a, b) if os.path.exists(f'{W}/en/{p}.html')]


def yof(L, v, pitch):
    v = float(v)
    i = int(v)
    if v < 1:
        return TOP + (L[0][0] - (1 - v) * pitch) * SC
    if v > len(L):
        return TOP + (L[-1][0] + (v - len(L)) * pitch) * SC
    y = L[i - 1][0]
    if v > i and i < len(L):
        y += (L[i][0] - L[i - 1][0]) * (v - i)
    return TOP + y * SC


def head_y(p, d, pitch):
    """top of the printed folio: lines.py's folio box, else the first solid ink run above line 1"""
    L = d['lines']
    if d.get('folio'):
        return TOP + d['folio'][0] * SC
    g = np.asarray(Image.open(f'{W}/scan/s{p}.png').convert('L'))
    x0, x1 = d['col']
    lim = L[0][0] - 4 if L else int(d['h'] * .2)
    rows = (g[:lim, x0:x1] < 120).sum(1) >= 4
    run = 0
    for y in range(int(d['h'] * .025), lim):
        run = run + 1 if rows[y] else 0
        if run >= 10:
            return TOP + (y - 9) * SC
    return TOP + max(0, L[0][0] - 1.4 * pitch) * SC if L else TOP


out = []
for p in pages:
    d = json.load(open(f'{W}/lines/s{p}.json'))
    L = d['lines']
    pitch = float(np.median(np.diff([l[0] for l in L]))) if len(L) > 2 else 33.0 * G['scan_h'] / 1500
    f = open(f'{W}/en/s{p}.html').read()
    f = re.sub(r'data-l="(-?[\d.]+)"', lambda m: f'data-l="{m.group(1)}" data-y="{yof(L, m.group(1), pitch):.1f}"', f)
    f = re.sub(r'data-at="([\d.]+)"', lambda m: f'data-at="{m.group(1)}" data-y="{TOP + float(m.group(1)) * SC:.1f}"', f)
    f = re.sub(r'<p class="rh([^"]*)">', lambda m: f'<p class="rh{m.group(1)}" data-y="{head_y(p, d, pitch):.1f}">', f)
    x = HALF + (HALF - TW) / 2
    fs = re.search(r'<!--\s*fs=([\d.]+)\s*-->', f)
    lh = re.search(r'<!--\s*lh=([\d.]+)\s*-->', f)
    if fs:
        att = f' data-fs="{fs.group(1)}"'
    elif len(L) >= 8:               # base size from the German line pitch
        pt = float(np.median(np.diff([l[0] for l in L[1:]]))) * SC
        att = f' data-fs="{min(F["fs_max"], max(F["fs_min"], round((pt / 1.24 - 0.4) * 4) / 4))}"'
    else:
        att = ''
    if lh:
        att += f' data-lh="{lh.group(1)}"'
    if len(L) >= 8 and not fs:      # bottom of the German text block: fit.js may grow type down to it
        k = 1                       # stop at a gap > 4 lines (catchword, stamp, signature below the text)
        while k < len(L) and L[k][0] - L[k - 1][1] < 4 * pitch:
            k += 1
        att += f' data-end="{TOP + L[k - 1][1] * SC:.1f}"'
    att += f' data-grow="{F["grow"]}" data-max="{F["max"]}" data-drift="{F["drift"]}"'
    f = f.replace('src="orn/', f'src="file://{os.path.abspath(W)}/orn/')
    out.append(f'<div class="sheet" data-p="{p}"><div class="body" style="left:{x:.1f}pt;width:{TW}pt"{att}>\n'
               f'{f}\n</div></div>')

css = open(f'{HERE}/book.css').read()
if os.path.exists(f'{W}/extra.css'):
    css += '\n/* book-specific (extra.css) */\n' + open(f'{W}/extra.css').read()
css += (f'\n@page {{ size: {SW}pt {SH}pt; margin: 0; }}\n.sheet {{ width: {SW}pt; height: {SH}pt; }}\n'
        f'.body {{ height: {SH - 12}pt; }}\n')
js = open(f'{HERE}/fit.js').read()
open(OUT, 'w').write(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{css}</style></head><body>\n'
                     + '\n'.join(out) + f'\n<script>{js}</script></body></html>')
open(OUT + '.pages', 'w').write('\n'.join(pages) + '\n')
print(len(pages), 'pages ->', OUT)
