"""Which pages of each batch are still missing — the restart list after a usage-limit stop.
usage: status.py WORK            (reads WORK/batches.txt: lines "B01 006 027" / "R1 002 050")
A stopped translator with a large context costs a full cache rewrite to resume; for anything but a nearly finished
batch, launch a FRESH agent on the missing pages printed here instead of messaging the old one."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

W = sys.argv[1]
cfg = book.load(W)
tot = done = 0
if not os.path.exists(f'{W}/batches.txt'):
    sys.exit('no WORK/batches.txt (lines "B01 006 017")')
for line in open(f'{W}/batches.txt'):
    f = line.split()
    if len(f) < 3 or not f[0].startswith('B'):
        continue
    ps = book.pages(cfg, int(f[1]), int(f[2]))
    miss = [p for p in ps if not os.path.exists(f'{W}/en/{p}.html')]
    tot += len(ps); done += len(ps) - len(miss)
    print(f'{f[0]} {f[1]}-{f[2]}: {len(ps) - len(miss)}/{len(ps)}' + (f'  missing: {" ".join(miss)}' if miss else '  done'))
print(f'total {done}/{tot}')
