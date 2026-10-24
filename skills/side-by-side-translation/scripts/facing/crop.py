"""Enlarge a few lines of a page when a word is illegible on the bundle's views (rarely needed).
usage: crop.py WORK sPPP FIRSTLINE LASTLINE [all|text|notes]   -> WORK/crops/crop-sPPP-A-B.png (2x), path printed"""
import sys, json, os
from PIL import Image
W, p, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
side = sys.argv[5] if len(sys.argv) > 5 else 'text'
d = json.load(open(f'{W}/lines/{p}.json'))
L = d['lines']
a = max(1, a); b = min(len(L), b)
y0, y1 = max(0, L[a - 1][0] - 12), min(d['h'], L[b - 1][1] + 12)
im = Image.open(f'{W}/scan/{p}.png')
x0, x1 = 0, d['w']
if side == 'text':
    x0, x1 = d['col'][0] - 10, d['col'][1] + 10
elif side == 'notes' and d['mcol']:
    x0, x1 = d['mcol'][0] - 10, d['mcol'][1] + 10
im = im.crop((x0, y0, x1, y1))
im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
os.makedirs(f'{W}/crops', exist_ok=True)
out = os.path.abspath(f'{W}/crops/crop-{p}-{a}-{b}-{side}.png')
im.save(out)
print(out)
