"""Detect text lines on each whitened scan by projection profiles.
scan/sPPP.png -> lines/sPPP.json  {w,h, col:[x0,x1], mcol:[x0,x1]|null, side:'L'|'R'|null,
                                   lines:[[top,bot,x0,x1],...], mlines:[[top,bot,x0,x1],...]}
and zoom/sPPP.png: the scan with line numbers (red, main column) and margin numbers (blue, m1..)
for the translators.  usage: lines.py WORK [pages...]"""
import sys, glob, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W = sys.argv[1]
sel = set(sys.argv[2:])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book
MARGIN_NOTES = book.load(W).get("margin_notes", False)   # book.json: true when the print has marginal notes
FONT = FONT_S = None                     # overlay labels: first sans-serif found (macOS, Linux, Windows)
for _bold, _reg in (('/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf'),
                    ('/Library/Fonts/Arial Bold.ttf', '/Library/Fonts/Arial.ttf'),
                    ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                    ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
                    ('/usr/share/fonts/TTF/DejaVuSans-Bold.ttf', '/usr/share/fonts/TTF/DejaVuSans.ttf'),
                    ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf')):
    try:
        FONT, FONT_S = ImageFont.truetype(_bold, 22), ImageFont.truetype(_reg, 15)
        break
    except Exception:
        continue
if FONT is None:
    try:
        FONT, FONT_S = ImageFont.load_default(size=22), ImageFont.load_default(size=15)
    except TypeError:
        FONT = FONT_S = ImageFont.load_default()


def runs(mask, mingap=1, minlen=1):
    r, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        elif not v and s is not None:
            r.append([s, i]); s = None
    if s is not None:
        r.append([s, len(mask)])
    # merge across small gaps
    m = []
    for a in r:
        if m and a[0] - m[-1][1] < mingap:
            m[-1][1] = a[1]
        else:
            m.append(a)
    return [a for a in m if a[1] - a[0] >= minlen]


def smooth(v, k):
    return np.convolve(v, np.ones(k) / k, mode='same')


def pitch(prof):
    """line pitch by autocorrelation of the row profile"""
    p = prof - prof.mean()
    ac = np.correlate(p, p, mode='full')[len(p) - 1:]
    lo, hi = 18, 90          # first strong peak (argmax alone often picks 2x the pitch)
    a = ac[lo:hi]
    for i in range(1, len(a) - 1):
        if a[i] >= a[i - 1] and a[i] >= a[i + 1] and a[i] > 0.25 * ac[0]:
            return lo + i
    return lo + int(np.argmax(a))


def textlines(ink, x0, x1, pitch_hint=None):
    """ink: bool array; returns [[top,bot,lx0,lx1]] within columns x0..x1."""
    sub = ink[:, x0:x1]
    prof = smooth(sub.mean(1), 3)
    on = prof > max(0.004, prof.max() * 0.03)   # low threshold keeps short last lines
    rr = runs(on, mingap=3, minlen=6)
    # split over-tall runs (touching lines) at profile minima
    med = pitch(prof)
    out = []
    for a, b in rr:
        if b - a > 1.6 * med:
            n = round((b - a) / med)
            cuts = [a]
            for k in range(1, n):
                c = a + (b - a) * k // n
                lo, hi = c - med // 3, c + med // 3
                c = lo + int(np.argmin(prof[lo:hi]))
                cuts.append(c)
            cuts.append(b)
            out += [[cuts[i], cuts[i + 1]] for i in range(n)]
        else:
            out.append([a, b])
    res = []
    for a, b in out:
        cols = np.where(sub[a:b].any(0))[0]
        if len(cols) == 0:
            continue
        res.append([int(a), int(b), int(x0 + cols[0]), int(x0 + cols[-1])])
    return res


def page(f):
    name = os.path.basename(f)[:-4]
    g = np.asarray(Image.open(f).convert('L'), dtype=np.uint8)
    h, w = g.shape
    ink = g < 120
    # ignore neighbour-page strips / binding edges
    ink[:, :int(w * .045)] = False
    ink[:, int(w * .965):] = False
    # neighbour-page strips that run in from the image edge
    fp = smooth(ink[int(h * .1):int(h * .9)].mean(0), 3)
    for xs in (range(int(w * .045), int(w * .11)), range(int(w * .965) - 1, int(w * .89), -1)):
        xs = list(xs)
        if fp[xs[0]] > 0.03:
            for x in xs:
                if fp[x] < 0.01:
                    if xs[0] < x:
                        ink[:, :x] = False
                    else:
                        ink[:, x:] = False
                    break
    ink[:int(h * .02)] = False
    ink[int(h * .985):] = False
    colprof = smooth(ink[int(h * .1):int(h * .95)].mean(0), 9)
    # text column = widest run of dense ink; margin notes = sparse ink beside it
    cr = runs(colprof > 0.03, mingap=40, minlen=8)   # full ink extent (higher thresholds split columns)
    cr.sort(key=lambda a: a[1] - a[0], reverse=True)
    col = list(cr[0]) if cr else [int(w * .1), int(w * .9)]
    if col[1] - col[0] < .45 * w:     # short / display pages
        col = [int(w * .08), int(w * .93)]
    mcol, side = None, None
    rows = ink[int(h * .08):int(h * .96)]
    best = 0
    for sd, (a, b) in (('R', (col[1] + 6, min(w, col[1] + int(w * .2)))), ('L', (max(0, col[0] - int(w * .2)), col[0] - 6))):
        if b - a < 20:
            continue
        r = rows[:, a:b]
        nrows = r.any(1).sum()
        if nrows > 25 and nrows > best:
            xs = np.where(r.any(0))[0]
            best = nrows
            mcol, side = [a + int(xs[0]), a + int(xs[-1]) + 1], sd
    if not MARGIN_NOTES:      # pencil marks and stamps beside the text are not notes
        mcol, side = None, None
    # widen the main column slightly but never into the margin column
    x0, x1 = max(0, col[0] - 8), min(w, col[1] + 8)
    if side == 'R':
        x1 = min(x1, mcol[0] - 2)
    if side == 'L':
        x0 = max(x0, mcol[1] + 2)
    lines = [l for l in textlines(ink, x0, x1) if l[1] - l[0] >= 12]
    # a folio line at the top is never numbered: red 1 = first text line; build.py places p.rh at d["folio"]
    folio = None
    if len(lines) >= 8:
        a, b, lx0, lx1 = lines[0]
        if a < 0.11 * h and (b - a <= 22 or (lx1 - lx0) < 0.3 * (x1 - x0)) and lines[1][0] - b > 12:
            folio = lines.pop(0)
    mlines = []
    if mcol:  # note blocks (not single lines): runs separated by clear gaps
        sub = ink[:, mcol[0]:mcol[1]]
        for a, b in runs(smooth(sub.mean(1), 3) > 0.01, mingap=16, minlen=8):
            xs = np.where(sub[a:b].any(0))[0]
            mlines.append([int(a), int(b), int(mcol[0] + xs[0]), int(mcol[0] + xs[-1])])
    # the running head often straddles the margin column: merge margin lines lying inside it
    d = dict(w=w, h=h, col=[x0, x1], mcol=mcol, side=side, lines=lines, mlines=mlines, folio=folio)
    json.dump(d, open(f'{W}/lines/{name}.json', 'w'))
    # numbered overlay
    im = Image.open(f).convert('RGB')
    pad = 70
    canvas = Image.new('RGB', (w + 2 * pad + 40, h), 'white')
    canvas.paste(im, (pad, 0))
    dr = ImageDraw.Draw(canvas)
    for i, (a, b, lx0, lx1) in enumerate(lines, 1):
        y = (a + b) // 2 - 11
        dr.text((4, y), str(i), fill=(220, 0, 0), font=FONT)
        dr.line([(pad + lx0, b), (pad + lx0 + 25, b)], fill=(220, 0, 0), width=2)
    # blue pixel ruler on the right (scan y in px) for data-at anchors
    rx = w + 2 * pad - 62
    for yy in range(0, h, 25):
        dr.line([(rx, yy), (rx + (14 if yy % 100 else 26), yy)], fill=(0, 90, 220), width=2 if yy % 100 == 0 else 1)
        if yy % 100 == 0 and yy:
            dr.text((rx + 28, yy - 11), str(yy), fill=(0, 90, 220), font=FONT_S)
    canvas.save(f'{W}/zoom/{name}.png', optimize=True)
    return name, len(lines), len(mlines), side


for f in sorted(glob.glob(f'{W}/scan/s*.png')):
    n = os.path.basename(f)[:-4]
    if sel and n not in sel:
        continue
    print(*page(f))
