"""Put the scan into the left half of every rendered English sheet.
usage: merge.py WORK OUT.pdf part1.pdf part1.html.pages [part2.pdf part2.html.pages ...]
With WORK/clean.pdf (the source PDF reduced to its scan image by prep.py) the page is merged vector-crisp, as is;
without it (camera images) WORK/scan/sPPP.png is embedded as greyscale JPEG.  Geometry from book.json."""
import sys, os, io
from pypdf import PdfReader, PdfWriter, Transformation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W, OUT = sys.argv[1], sys.argv[2]
parts = list(zip(sys.argv[3::2], sys.argv[4::2]))
G = book.load(W)['geometry']
SC, TOP, HALF, PH = G['sc'], G['top'], G['half'], G['sheet'][1]
SHT = G['scan_h'] * SC                       # displayed scan height, pt
src = PdfReader(f'{W}/clean.pdf') if os.path.exists(f'{W}/clean.pdf') else None


def raster(p):
    from PIL import Image
    im = Image.open(f'{W}/scan/s{p}.png').convert('L')
    buf = io.BytesIO()
    im.save(buf, 'PDF', resolution=im.height / (SHT / 72), quality=70)
    return PdfReader(io.BytesIO(buf.getvalue())).pages[0]


wr = PdfWriter()
for pdf, lst in parts:
    pages = open(lst).read().split()
    rd = PdfReader(pdf)
    assert len(rd.pages) == len(pages), (pdf, len(rd.pages), len(pages))
    for page, p in zip(rd.pages, pages):
        newp = wr.add_page(page)
        sp = src.pages[int(p) - 1] if src else raster(p)
        mb = sp.mediabox
        pw, ph = float(mb.width), float(mb.height)
        k = SHT / ph
        x = (HALF - pw * k) / 2 + 6 - float(mb.left) * k
        y = PH - TOP - SHT - float(mb.bottom) * k
        newp.merge_transformed_page(sp, Transformation().scale(k, k).translate(x, y), over=True)
for pg in wr.pages:
    pg.compress_content_streams()
wr.compress_identical_objects()
with open(OUT, 'wb') as fh:
    wr.write(fh)
print(OUT, os.path.getsize(OUT) // 1024, 'KB', len(wr.pages), 'pages')
