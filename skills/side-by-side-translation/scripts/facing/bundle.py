"""Everything one page needs, in ONE call — for translators and reviewers.
usage: bundle.py WORK sPPP [sPPP ...] [--en] [--no-views]

Prints per page: the expected folio and printer's signatures, the edge lines of the neighbouring pages
(and of their English, if written), then the OCR LINE BY LINE, numbered exactly like the red numbers:
    L12 ¶  text      ¶ = indented line (paragraph start)    c = centred line
    L13 ⏎  text      ⏎ = line ends short (paragraph end)    ‹wort› = probably letter-spaced (Sperrdruck)
plus printed rules ("rule y=1290 after L33" — y is a data-at value) and words in the margins.
Writes WORK/view/sPPP-1.png [-2.png]: the text block at reading size, red line numbers left, blue scan-y
ruler right, each image <= 1.15 MP so Read shows it undownscaled.  --en appends the current English page\n(and the original transcription, for retypeset editions).
Word boxes come from WORK/ocr/sPPP.tsv (x0 y0 x1 y1 word, scan px), made on first use from the PDF text
layer (book.json ocr.pdf) or, if that has no usable text, from tesseract (ocr.tesseract language)."""
import sys, os, re, json, subprocess, statistics, html
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

args = [a for a in sys.argv[1:] if not a.startswith('--')]
W, PAGES = args[0], args[1:]
EN = '--en' in sys.argv
VIEWS = '--no-views' not in sys.argv
cfg = book.load(W)
MAXPX = 1_150_000
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


# ---------- word boxes ----------
def boxes_from_pdf(p, w, h):
    o = cfg['ocr']
    pdf = os.path.join(W, o['pdf'])
    if not os.path.exists(pdf):
        return []
    n = p + o.get('pdf_offset', 0)
    r = subprocess.run(['pdftotext', '-f', str(n), '-l', str(n), '-bbox', pdf, '-'],
                       capture_output=True, text=True)
    m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', r.stdout)
    if not m:
        return []
    pw, ph = float(m.group(1)), float(m.group(2))
    dx = dy = 0.0
    if o.get('align') == 'mediabox' and os.path.exists(f'{W}/clean.pdf'):
        # clean.pdf page = source page with the mediabox moved onto the scan image (HathiTrust-style prep)
        from pypdf import PdfReader
        cb = PdfReader(f'{W}/clean.pdf').pages[p - 1].mediabox
        sb = PdfReader(pdf).pages[n - 1].mediabox
        dx, dy = float(cb.left) - float(sb.left), float(sb.top) - float(cb.top)
        pw, ph = float(cb.width), float(cb.height)
    kx, ky = w / pw, h / ph
    out = []
    for x0, y0, x1, y1, t in re.findall(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', r.stdout):
        out.append(((float(x0) - dx) * kx, (float(y0) - dy) * ky, (float(x1) - dx) * kx, (float(y1) - dy) * ky,
                    html.unescape(t)))
    return out


def boxes_from_tesseract(p):
    lang = cfg['ocr'].get('tesseract', 'deu')
    im = Image.open(f'{W}/scan/s{p:03d}.png').convert('L')
    big = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    tmp = f'{W}/view/.t{p:03d}.png'
    big.save(tmp)
    r = subprocess.run(['tesseract', tmp, '-', '-l', lang, '--psm', '4', 'tsv'], capture_output=True, text=True)
    os.remove(tmp)
    out = []
    for row in r.stdout.splitlines()[1:]:
        c = row.split('\t')
        if len(c) == 12 and c[0] == '5' and c[11].strip():
            x, y, ww, hh = (int(v) / 2 for v in c[6:10])
            out.append((x, y, x + ww, y + hh, c[11]))
    return out


def word_boxes(p, w, h, nlines):
    f = f'{W}/ocr/s{p:03d}.tsv'
    if os.path.exists(f):
        return [(*map(float, r.split('\t')[:4]), r.split('\t', 4)[4]) for r in open(f).read().splitlines() if r]
    b = boxes_from_pdf(p, w, h)
    if len(b) < 6 * max(1, nlines) // 2:      # no usable text layer on this page
        b = boxes_from_tesseract(p)
    os.makedirs(f'{W}/ocr', exist_ok=True)
    with open(f, 'w') as fh:
        for x0, y0, x1, y1, t in b:
            fh.write(f'{x0:.1f}\t{y0:.1f}\t{x1:.1f}\t{y1:.1f}\t{t}\n')
    return b


# ---------- page analysis ----------
def rules(g):
    ink = g < 150
    h, w = ink.shape
    out, y = [], int(h * .03)
    while y < h - 2:
        xs = np.where(ink[y])[0]
        if len(xs) > 0.08 * w:
            br = np.where(np.diff(xs) > 3)[0]
            st, en = np.r_[xs[0], xs[br + 1]], np.r_[xs[br], xs[-1]]
            k = int(np.argmax(en - st))
            if en[k] - st[k] > 0.08 * w:
                y0 = y
                while y < h - 1 and ink[y + 1, st[k]:en[k]].mean() > 0.5:
                    y += 1
                if y - y0 <= 8 and ink[max(0, y0 - 4):y0 - 1, st[k]:en[k]].mean() < .15 \
                        and ink[y + 2:y + 6, st[k]:en[k]].mean() < .15:
                    out.append((y0, int(st[k]), int(en[k])))
        y += 1
    return out


def analyse(p):
    d = json.load(open(f'{W}/lines/s{p:03d}.json'))
    L = d['lines']
    g = np.asarray(Image.open(f'{W}/scan/s{p:03d}.png').convert('L'))
    h, w = g.shape
    pitch = float(np.median(np.diff([l[0] for l in L]))) if len(L) > 2 else 33.0
    words = word_boxes(p, w, h, len(L))
    x0c, x1c = d['col']
    rows = [[] for _ in L]
    head, foot, margin, loose = [], [], [], []
    for b in words:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if cx < x0c - 0.5 * pitch or cx > x1c + 0.5 * pitch:
            margin.append(b); continue
        best, bd = None, 1e9
        for i, (t, bt, lx0, lx1) in enumerate(L):
            if t - 0.3 * pitch <= cy <= bt + 0.3 * pitch:
                dd = abs(cy - (t + bt) / 2)
                if dd < bd:
                    best, bd = i, dd
        if best is not None:
            rows[best].append(b)
        elif L and cy < L[0][0]:
            head.append(b)
        elif L and cy > L[-1][1]:
            foot.append(b)
        else:
            loose.append(b)
    # letter-spacing (Sperrdruck): blank columns between the letters of a word; normal type has almost none
    mingap = max(3, round(0.12 * pitch))

    def gaps(b, line):
        sub = g[int(line[0]):int(line[1]), max(0, int(b[0])):int(b[2]) + 1] < 140
        run, n = 0, 0
        for v in sub.any(0):
            if not v:
                run += 1
            else:
                n += run >= mingap
                run = 0
        return n

    def fmt(r, line):
        r = sorted(r)
        flags = []
        for b in r:
            n = len(re.sub(r'\W', '', b[4]))
            k = gaps(b, line) if n >= 2 else 0
            spaced = n >= 2 and k / (n - 1) >= 0.45 and (n > 3 or k >= 2)   # short words: >= 2 gaps
            flags.append(2 if spaced else (1 if k else 0))
        for i, f in enumerate(flags):           # short words with some spacing next to a spaced word
            if f == 1 and ((i and flags[i - 1] == 2) or (i + 1 < len(flags) and flags[i + 1] == 2)):
                flags[i] = 3
        toks, i = [], 0
        while i < len(r):
            if flags[i] >= 2:
                j = i
                while j < len(r) and flags[j] >= 2:
                    j += 1
                toks.append('‹' + ' '.join(b[4] for b in r[i:j]) + '›'); i = j
            else:
                toks.append(r[i][4]); i += 1
        return ' '.join(toks)

    left = statistics.median([l[2] for l in L]) if L else 0
    right = statistics.median([l[3] for l in L]) if L else w
    marks = []
    for i, (t, bt, lx0, lx1) in enumerate(L):
        m = ' '
        if lx0 - left > 1.6 * pitch and right - lx1 > 1.6 * pitch:
            m = 'c'
        elif lx0 - left > 0.5 * pitch:
            m = '¶'
        elif right - lx1 > 1.5 * pitch and i < len(L) - 1:
            m = '⏎'
        marks.append(m)
    rl = []
    for y0, a, b in rules(g):
        k = sum(1 for l in L if l[1] < y0)
        rl.append(f'rule y={y0} after L{k}' if k else f'rule y={y0} above L1')
    return dict(d=d, L=L, g=g, w=w, h=h, pitch=pitch, rows=rows, marks=marks, fmt=fmt,
                head=head, foot=foot, margin=margin, loose=loose, rules=rl)


def plain(r):
    return ' '.join(b[4] for b in sorted(r))


def en_edge(p, last):
    f = f'{W}/en/s{p:03d}.html'
    if not os.path.exists(f):
        return None
    s = open(f).read()
    s = re.sub(r'<p class="(rh|sig|sigf|cw)[^"]*".*?</p>', ' ', s, flags=re.S)
    s = re.sub(r'<!--.*?-->', ' ', s)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', s)).split()
    return ' '.join(t[-12:] if last else t[:12])


def neighbour(p, last):
    """edge OCR line of the nearest non-dropped neighbour"""
    q = p - 1 if last else p + 1
    while f's{q:03d}' in cfg['drop']:
        q = q - 1 if last else q + 1
    if not (cfg['first'] <= q <= cfg['last']) or not os.path.exists(f'{W}/lines/s{q:03d}.json'):
        return q, None, None
    a = analyse(q)
    rows = [r for r in a['rows'] if r]
    txt = plain(rows[-1]) if (last and rows) else (plain(rows[0]) if rows else '')
    return q, txt, en_edge(q, last)


# ---------- views ----------
def views(p, a):
    L, g, d, pitch = a['L'], a['g'], a['d'], a['pitch']
    h, w = a['h'], a['w']
    n = len(L)
    if n == 0:
        groups = [(0, 0)]
    elif n <= 22:
        groups = [(1, n)]
    else:
        mid = n // 2
        cands = [k for k in range(mid - 3, mid + 4) if 1 <= k < n and a['marks'][k] == '¶']
        k = min(cands, key=lambda k: abs(k - mid)) if cands else mid
        groups = [(1, k), (k + 1, n)]
    xs = [l[2] for l in L] + [d['col'][0]]
    xe = [l[3] for l in L] + [d['col'][1]]
    for b in a['margin']:
        xs.append(b[0]); xe.append(b[2])
    X0, X1 = max(0, int(min(xs)) - 14), min(w, int(max(xe)) + 14)
    out = []
    os.makedirs(f'{W}/view', exist_ok=True)
    for gi, (s, e) in enumerate(groups, 1):
        if n == 0:
            Y0, Y1 = int(h * .03), int(h * .97)
        else:
            Y0 = int(L[s - 1][0] - 0.6 * pitch) if s > 1 else int(h * .02)
            Y1 = int(L[e - 1][1] + 0.6 * pitch) if e < n else int(h * .985)
        ink = np.where((g[Y0:Y1, X0:X1] < 140).sum(1) >= 3)[0]   # trim blank paper above/below
        if len(ink):
            Y0, Y1 = max(0, Y0 + int(ink[0]) - 12), min(h, Y0 + int(ink[-1]) + 14)
        cw, ch = X1 - X0, Y1 - Y0
        gut_l, gut_r = 46, 58
        f = 2.0                             # largest scale <= 2x that keeps the image under MAXPX
        while (cw * f + gut_l + gut_r) * ch * f > MAXPX:
            f -= 0.02
        crop = Image.fromarray(g[Y0:Y1, X0:X1]).resize((int(cw * f), int(ch * f)), Image.LANCZOS).convert('RGB')
        im = Image.new('RGB', (crop.width + gut_l + gut_r, crop.height), 'white')
        im.paste(crop, (gut_l, 0))
        dr = ImageDraw.Draw(im)
        for i in range(s, e + 1) if n else []:
            t, bt, lx0, lx1 = L[i - 1]
            y = ((t + bt) / 2 - Y0) * f
            dr.text((2, y - 12), str(i), fill=(220, 0, 0), font=FONT)
            yb = (bt - Y0) * f
            xa = gut_l + (lx0 - X0) * f
            dr.line([(xa, yb + 1), (xa + 22, yb + 1)], fill=(220, 0, 0), width=2)
        rx = gut_l + crop.width + 4
        for yy in range((Y0 // 25 + 1) * 25, Y1, 25):
            yv = (yy - Y0) * f
            big = yy % 100 == 0
            dr.line([(rx, yv), (rx + (16 if big else 8), yv)], fill=(0, 90, 220), width=2 if big else 1)
            if big:
                dr.text((rx + 18, yv - 9), str(yy), fill=(0, 90, 220), font=FONT_S)
        path = os.path.abspath(f'{W}/view/s{p:03d}-{gi}.png')
        im.save(path, optimize=True)
        out.append(f'{path} ({"L%d–%d" % (s, e) if n else "whole page"})')
    return out


# ---------- output ----------
for ps in PAGES:
    p = int(ps.lstrip('s'))
    a = analyse(p)
    exp = book.expected_folio(cfg, p)
    mk = book.expected_marks(cfg, p)
    pn = book.printed(cfg, p)
    print(f'=== s{p:03d} · printed p. {pn or "—"} · folio {exp or "none printed"} · '
          f'signature {", ".join(f"{c} {t}" for c, t in mk) if mk else "none"}')
    if VIEWS:
        print('views:', '  '.join(views(p, a)))
    q, t, e = neighbour(p, True)
    if t is not None:
        print(f'prev s{q:03d} ends:   {t}' + (f'\n   its English ends: …{e}' if e else ''))
    q, t, e = neighbour(p, False)
    if t is not None:
        print(f'next s{q:03d} begins: {t}' + (f'\n   its English begins: {e}…' if e else ''))
    if a['head']:
        print('above L1:', plain(a['head']))
    for i, r in enumerate(a['rows']):
        print(f'L{i + 1:<3}{a["marks"][i]} {a["fmt"](r, a["L"][i])}')
    if a['foot']:
        print('below last line:', plain(a['foot']))
    if a['loose']:
        print('between lines (unplaced):', plain(a['loose']))
    if a['margin']:
        print('margin:', plain(a['margin']))
    for r in a['rules']:
        print(r)
    if EN:
        for sub, label in (('orig', 'Original (retypeset text)'), ('en', 'English')):
            f = f'{W}/{sub}/s{p:03d}.html'
            if sub == 'orig' and not os.path.isdir(f'{W}/orig'):
                continue
            print(f'--- {label}', f, '---')
            print(open(f).read().rstrip() if os.path.exists(f) else '(not written)')
    print()
