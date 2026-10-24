"""Cut an ornament (headpiece, tailpiece, rule, FIN device) from the clean scan for use in the English page.
usage: orn.py WORK sPPP NAME TOP BOTTOM [X0 X1]     (scan px = blue-ruler y; x = zoom x minus 70)
Writes work/orn/sPPP_NAME.png and prints the HTML block to paste (anchored at TOP, same width as in the scan)."""
import sys, subprocess, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book
import numpy as np
from PIL import Image
from pypdf import PdfReader
W, p, name, t, b = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
SC = book.load(W)["geometry"]["sc"]
g = np.asarray(Image.open(f'{W}/scan/{p}.png').convert('L'))
if len(sys.argv) > 7:
    x0, x1 = int(sys.argv[6]), int(sys.argv[7])
else:
    cols = np.where((g[t:b] < 140).sum(0) > 0)[0]
    x0, x1 = int(cols[0]) - 3, int(cols[-1]) + 4
rows = np.where((g[t:b, x0:x1] < 140).sum(1) > 0)[0]
t, b = t + int(rows[0]) - 2, t + int(rows[-1]) + 3
ph = float(PdfReader(f'{W}/clean.pdf').pages[int(p[1:]) - 1].mediabox.height)
k = ph / book.load(W)['geometry']['scan_h']   # scan px -> pdf pt
dpi = 450
r = dpi / 72
out = f'{W}/orn/{p}_{name}'
subprocess.run(['pdftoppm', '-r', str(dpi), '-gray', '-png', '-singlefile', '-f', p[1:], '-l', p[1:],
                '-x', str(int(x0 * k * r)), '-y', str(int(t * k * r)), '-W', str(int((x1 - x0) * k * r)),
                '-H', str(int((b - t) * k * r)), f'{W}/clean.pdf', out], check=True)
im = np.asarray(Image.open(out + '.png').convert('L')).astype(float)
im = np.clip((im - 40) * 255 / (215 - 40), 0, 255)          # whiten paper, deepen ink
Image.fromarray(im.astype(np.uint8)).save(out + '.png', optimize=True)
print(f'<p class="orn" data-at="{t}"><img src="orn/{os.path.basename(out)}.png" style="width:{(x1 - x0) * SC:.1f}pt"></p>')
