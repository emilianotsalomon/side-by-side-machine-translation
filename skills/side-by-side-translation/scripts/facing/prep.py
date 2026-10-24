"""Source PDF -> WORK/clean.pdf (scan image only: library stamps, watermarks, backgrounds and the invisible OCR
removed — merged later onto the left half, vector-crisp) + WORK/scan/sPPP.png (greyscale, scan_h px tall: what
lines.py and bundle.py read).  Word boxes for bundle.py come later, on first use, from the source's text layer
(book.json ocr.pdf) or from tesseract.
usage: prep.py WORK KIND [--flat] [--pages A-B]      source = WORK/src/orig.pdf (images: WORK/raw/*.jpg|png|jp2)
KIND  ia      Internet Archive MRC PDF: drop the fzImg0 background draw (paper, show-through, "Digitized by
              Google") and BT…ET; the masked ink layer stays.
      google  Google Books PDF: keep only the /GS1 image draws (ALL of them — some pages are JBIG2 + JPX layers,
              keeping one renders blank); drops the /Wm stamp and the OCR text.
      hathi   HathiTrust PDF: keep only the /Ix… or /Jx… scan image and move the mediabox onto it (drops the Hathi
              margin watermark, the Google logo, the /CBJ stamp form and the OCR).  Sets ocr.align = mediabox.
      plain   any other PDF (born-digital or already clean): pages used as they are.
      images  camera scans in WORK/raw/: whitened, deskewed, cropped to one frame around the text block; no
              clean.pdf (merge.py embeds the PNGs).
--flat   flatten uneven lighting (dark/blotchy scans) before writing scan/ (the left page stays the clean PDF).
Look at 3-4 scan/ PNGs afterwards (one montage) before running lines.py."""
import sys, re, os, glob, json, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W, KIND = sys.argv[1], sys.argv[2]
FLAT = '--flat' in sys.argv
cfg = book.load(W)
H = cfg['geometry']['scan_h']
for d in ('scan', 'ocr'):
    os.makedirs(f'{W}/{d}', exist_ok=True)


def flatten(im):
    w, h = im.size
    small = im.resize((max(1, w // 8), max(1, h // 8)), Image.BOX).filter(ImageFilter.MaxFilter(7)) \
        .filter(ImageFilter.GaussianBlur(6))
    bg = np.asarray(small.resize((w, h), Image.BILINEAR)).astype(float)
    r = np.clip(np.asarray(im).astype(float) / np.maximum(bg, 30), 0, 1.2)
    return Image.fromarray((np.clip((r - 0.30) / 0.50, 0, 1) ** 1.25 * 255).astype(np.uint8))


def clean_pdf():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject, RectangleObject
    rd = PdfReader(f'{W}/src/orig.pdf')
    wr = PdfWriter()
    for pg in rd.pages:
        p = wr.add_page(pg)
        if KIND == 'plain':
            continue
        s = pg.get_contents().get_data().decode('latin1')
        res = p['/Resources']
        keep = None
        if KIND == 'ia':
            s = re.sub(r'\bBT\b.*?\bET\b', '', s, flags=re.S)
            s = re.sub(r'q\s+[-\d.\s]+cm\s*/fzImg0 Do\s*Q', '', s)
            if '/fzImg0' in res.get('/XObject', {}):
                del res['/XObject']['/fzImg0']
            keep = s
        elif KIND == 'google':
            ms = list(re.finditer(r'q\s*/GS1 gs [^\n]*? cm /(\w+) Do\s*Q', s))
            if ms:
                keep = '\n'.join(m.group(0) for m in ms)
                names = {'/' + m.group(1) for m in ms}
                for k in list(res['/XObject'].keys()):
                    if k not in names:
                        del res['/XObject'][k]
        elif KIND == 'hathi':
            m = re.search(r'q\s+([\d.]+) 0 0 ([\d.]+) ([\d.]+) ([\d.]+) cm /([IJ]x\w+) Do Q', s)
            if m:
                keep = m.group(0)
                for k in list(res['/XObject'].keys()):
                    if k != '/' + m.group(5):
                        del res['/XObject'][k]
                w, h, x, y = map(float, m.group(1, 2, 3, 4))
                p.mediabox = p.cropbox = RectangleObject([x, y, x + w, y + h])
        if keep is not None:
            new = DecodedStreamObject()
            new.set_data(keep.encode('latin1') + b'\n')
            p[NameObject('/Contents')] = wr._add_object(new)
            for k in ('/Font', '/ExtGState') if KIND == 'hathi' else ('/Font',):
                if k in res:
                    del res[k]
    for pg in wr.pages:
        pg.compress_content_streams()
    with open(f'{W}/clean.pdf', 'wb') as fh:
        wr.write(fh)
    return len(rd.pages)


def render(i):
    out = f'{W}/scan/s{i:03d}'
    subprocess.run(['pdftoppm', '-f', str(i), '-l', str(i), '-scale-to-y', str(H), '-scale-to-x', '-1', '-gray',
                    '-png', '-singlefile', f'{W}/clean.pdf', out], check=True, stderr=subprocess.DEVNULL)
    if FLAT:
        flatten(Image.open(out + '.png').convert('L')).save(out + '.png', optimize=True)


# ---------- camera images ----------
def smooth(v, k):
    return np.convolve(v, np.ones(k) / k, mode='same')


def runs(mask, mingap=1):
    r, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        elif not v and s is not None:
            r.append([s, i]); s = None
    if s is not None:
        r.append([s, len(mask)])
    m = []
    for a in r:
        if m and a[0] - m[-1][1] < mingap:
            m[-1][1] = a[1]
        else:
            m.append(a)
    return m


def whiten(im):
    a = np.asarray(im, dtype=np.float32)
    bg = np.asarray(im.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(25)), dtype=np.float32)
    r = np.clip(a / np.maximum(bg, 1), 0, 1)
    return (np.clip((r - 0.30) / 0.48, 0, 1) ** 1.1 * 255).astype(np.uint8)


def skew(g):
    h, w = g.shape
    c = Image.fromarray(g[int(h * .15):int(h * .85), int(w * .15):int(w * .85)])
    best, ba = -1, 0.0
    for a in np.arange(-2.5, 2.51, 0.1):
        v = (np.asarray(c.rotate(a, resample=Image.BILINEAR, fillcolor=255)) < 128).mean(1).var()
        if v > best:
            best, ba = v, a
    return ba


def bbox(g):
    h, w = g.shape
    ink = g < 120
    ink[:, :int(w * .03)] = False; ink[:, int(w * .97):] = False
    ink[:int(h * .02)] = False; ink[int(h * .98):] = False
    cr = sorted(runs(smooth(ink[int(h * .15):int(h * .85)].mean(0), 15) > 0.03, mingap=40), key=lambda a: a[0] - a[1])
    x0, x1 = cr[0] if cr else (int(w * .1), int(w * .9))
    rp = smooth(ink[:, x0:x1].mean(1), 5)
    rr = [a for a in runs(rp > 0.004, mingap=60) if a[1] - a[0] > 6 and rp[a[0]:a[1]].mean() < 0.8]
    y0, y1 = (rr[0][0], rr[-1][1]) if rr else (int(h * .05), int(h * .95))
    return int(x0), int(y0), int(x1), int(y1)


def images():
    files = sorted(glob.glob(f'{W}/raw/*.jpg') + glob.glob(f'{W}/raw/*.png') + glob.glob(f'{W}/raw/*.jp2'))
    pre = {}
    for i, f in enumerate(files, 1):
        g = whiten(Image.open(f).convert('L'))
        a = skew(g)
        if abs(a) > 0.05:
            g = np.asarray(Image.fromarray(g).rotate(a, resample=Image.BICUBIC, fillcolor=255))
        pre[i] = (g, round(float(a), 2), bbox(g))
        print(i, os.path.basename(f), 'angle', pre[i][1], flush=True)
    bw = np.median([b[2] - b[0] for g, a, b in pre.values()])
    hs = sorted(b[3] - b[1] for g, a, b in pre.values() if b[3] - b[1] > 0.6 * g.shape[0]) or [0.8 * H]
    bh = hs[int(len(hs) * .97) - 1 if len(hs) > 3 else -1]
    fw, fh = int(bw * 1.16), int(bh * 1.05)
    for i, (g, a, (x0, y0, x1, y1)) in pre.items():
        h = g.shape[0]
        clean = np.full_like(g, 255)
        clean[max(0, y0 - 14):y1 + 14, max(0, x0 - 14):x1 + 14] = g[max(0, y0 - 14):y1 + 14, max(0, x0 - 14):x1 + 14]
        top = y0 - (fh - bh) / 2 if (y1 - y0) > 0.6 * h else (y0 + y1) / 2 - fh / 2
        canvas = Image.new('L', (fw, fh), 255)
        canvas.paste(Image.fromarray(clean), (-int(round((x0 + x1) / 2 - fw / 2)), -int(round(top))))
        canvas.resize((round(fw * H / fh), H), Image.LANCZOS).save(f'{W}/scan/s{i:03d}.png', optimize=True)
    return len(pre)


if KIND == 'images':
    n = images()
else:
    n = clean_pdf()
    sel = range(1, n + 1)
    if '--pages' in sys.argv:
        a, b = sys.argv[sys.argv.index('--pages') + 1].split('-')
        sel = range(int(a), int(b) + 1)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(render, sel))
    if KIND == 'hathi':
        bj = f'{W}/book.json'
        j = json.load(open(bj)) if os.path.exists(bj) else {}
        j.setdefault('ocr', {})['align'] = 'mediabox'
        json.dump(j, open(bj, 'w'), indent=1, ensure_ascii=False)
print('prep ok:', n, 'pages,', KIND, '(flat)' if FLAT else '')
