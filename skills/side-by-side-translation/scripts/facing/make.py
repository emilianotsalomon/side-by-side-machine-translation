"""Build the whole edition and report every check in one call — for BOTH layouts (book.json "layout").
usage: make.py WORK [OUT.pdf] [--checks-only] [-- extra build_pdf flags (retype layout only)]
  layout "facing" (photocopy edition, scan left / English right): runs check.py, seams.py, folios.py; builds and
      renders the English in chunks of 60 pages in parallel (headless Chrome), merges the scans, adds bookmarks and
      prints the fit report (pages whose type size changed, drift > 12pt, overflow — overflow is never acceptable).
  layout "retype" (clean-text edition, both columns typeset): runs check.py, seams.py, retype.py --check, then
      retype.py (→ build_pdf.py) with the settings in book.json "retype".
OUT defaults to book.json "out".  Python: whatever ran this script (use scripts/py)."""
import sys, os, subprocess, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

S = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
extra = argv[argv.index('--') + 1:] if '--' in argv else []
argv = argv[:argv.index('--')] if '--' in argv else argv
args = [a for a in argv if not a.startswith('--')]
W = os.path.abspath(args[0])        # render.sh needs absolute file:// paths
cfg = book.load(W)
OUT = os.path.abspath(os.path.expanduser(args[1] if len(args) > 1 else cfg['out']))
PY = sys.executable
LAYOUT = cfg.get('layout', 'facing')


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


checks = ('check.py', 'seams.py', 'folios.py') if LAYOUT == 'facing' else ('check.py', 'seams.py')
for name in checks:
    out = run(PY, f'{S}/{name}', W)
    print(f'--- {name}:', out or 'ok')
if LAYOUT == 'retype':
    print('--- retype.py --check:', run(PY, f'{S}/retype.py', W, '--check') or 'ok')
if '--checks-only' in argv:
    sys.exit()

if LAYOUT == 'retype':
    r = subprocess.run([PY, f'{S}/retype.py', W, OUT] + (['--'] + extra if extra else []))
    if r.returncode == 0 and os.path.exists(OUT):
        print(run('pdfinfo', OUT).split('Pages:')[1].split('\n')[0].strip() if run('pdfinfo', OUT) else '?',
              'pages,', os.path.getsize(OUT) // 1_000, 'KB ->', OUT)
    sys.exit(r.returncode)

T = f'{W}/build'
os.makedirs(T, exist_ok=True)
for f in glob.glob(f'{T}/p*.*'):
    os.remove(f)
pl = book.pages(cfg)
chunks = [pl[i:i + 60] for i in range(0, len(pl), 60)]
procs, parts = [], []
for c in chunks:
    a, b = int(c[0][1:]), int(c[-1][1:])
    h = f'{T}/p{a:03d}.html'
    print(run(PY, f'{S}/build.py', W, h, str(a), str(b)))
    procs.append(subprocess.Popen(['sh', f'{S}/render.sh', h, h[:-5] + '.pdf', h[:-5] + '.fit']))
    parts += [h[:-5] + '.pdf', h + '.pages']
for p in procs:
    p.wait()
fit = '\n'.join(open(f).read().strip() for f in sorted(glob.glob(f'{T}/p*.fit')) if open(f).read().strip())
open(f'{T}/fit.txt', 'w').write(fit + '\n')
bad = [l for l in fit.splitlines() if ' over=' in l and not l.split(' over=')[1].startswith(('0', '-'))]
drift = [l for l in fit.splitlines() if ' drift=' in l and int(l.split(' drift=')[1].split()[0]) > 12]
print(f'--- fit: {len(fit.splitlines())} pages with a type-size change (normal), {len(drift)} with drift>12, {len(bad)} OVERFLOWING')
for l in bad + drift[:20]:
    print('  ', l)
print(run(PY, f'{S}/merge.py', W, f'{T}/merged.pdf', *parts))
print(run(PY, f'{S}/outline.py', W, f'{T}/merged.pdf', OUT, *[p for p in parts if p.endswith('.pages')]))
info = run('pdfinfo', OUT)
print(info.split('Pages:')[1].split('\n')[0].strip() if 'Pages:' in info else '?', 'pages,',
      os.path.getsize(OUT) // 1_000_000, 'MB ->', OUT)
