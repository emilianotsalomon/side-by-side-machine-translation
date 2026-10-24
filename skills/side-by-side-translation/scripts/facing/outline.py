"""Add PDF bookmarks and metadata.  usage: outline.py WORK IN.pdf OUT.pdf pagelist...
Bookmarks from book.json "outline": [[scan, "Label", level], ...] (level 1 = top; deeper levels nest under the
previous shallower one); metadata from "meta": {"title", "author"}."""
import sys, os
from pypdf import PdfReader, PdfWriter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W, IN, OUT = sys.argv[1:4]
cfg = book.load(W)
pages = []
for lst in sys.argv[4:]:
    pages += open(lst).read().split()
rd = PdfReader(IN)
wr = PdfWriter(clone_from=rd)
assert len(rd.pages) == len(pages)
parents = {}
for item in cfg['outline']:
    scan, label = item[0], item[1]
    lvl = item[2] if len(item) > 2 else 1
    key = f'{scan:03d}'
    if key not in pages:
        print('outline: scan', scan, 'not in the edition, skipped'); continue
    parents[lvl] = wr.add_outline_item(label, pages.index(key), parent=parents.get(lvl - 1))
    for deeper in [l for l in parents if l > lvl]:
        del parents[deeper]
m = cfg['meta']
if m.get('title') or m.get('author'):
    wr.add_metadata({'/Title': m.get('title', ''), '/Author': m.get('author', '')})
if cfg['outline']:
    wr.page_mode = '/UseOutlines'
with open(OUT, 'wb') as fh:
    wr.write(fh)
print('outline ok', OUT, len(cfg['outline']), 'bookmarks')
