"""Build the whole edition and report every check in one call — for BOTH layouts (book.json "layout").
usage: make.py WORK [OUT.pdf] [--checks-only] [-- extra build_pdf flags (retype layout only)]
  layout "facing" (photocopy edition, scan left / English right): runs check.py, seams.py, folios.py; builds and
      renders the English in chunks of 60 pages in parallel (headless Chrome), merges the scans, adds bookmarks and
      prints the fit report (pages whose type size changed, drift > 12pt, overflow — overflow is never acceptable).
  layout "retype" (clean-text edition, both columns typeset): runs check.py, seams.py, retype.py --check, then
      retype.py (→ build_pdf.py) with the settings in book.json "retype".
OUT defaults to book.json "out".  Python: whatever ran this script (use scripts/py).
Exit status: 0 ok · 1 a step crashed or produced no output (its output is printed, nothing after it runs) ·
3 the PDF was built but pages overflow (listed in the fit report; overflow is never acceptable).
What the checks report (anchors, seams, folios) is for you to read and never changes the exit status."""
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
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        fail(f'{os.path.basename(cmd[1] if cmd[0] == PY else cmd[0])} exited {r.returncode}', out)
    return out


def fail(what, out=''):
    sys.stdout.flush()
    print(f'--- FAILED: {what}' + (f'\n{out}' if out else ''), file=sys.stderr)
    sys.exit(1)


def pages_of(pdf):
    info = run('pdfinfo', pdf)
    return info.split('Pages:')[1].split('\n')[0].strip() if 'Pages:' in info else '?'


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
    if r.returncode != 0:
        fail(f'retype.py exited {r.returncode}')
    if not os.path.exists(OUT):
        fail(f'retype.py wrote no {OUT}')
    print(pages_of(OUT), 'pages,', os.path.getsize(OUT) // 1_000, 'KB ->', OUT)
    sys.exit()

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
for p, pdf in zip(procs, parts[::2]):
    if p.returncode != 0 or not os.path.exists(pdf) or os.path.getsize(pdf) == 0:
        fail(f'render.sh {os.path.basename(pdf)}: ' + (f'exit {p.returncode}' if p.returncode else 'Chrome printed no PDF'))
fit = '\n'.join(open(f).read().strip() for f in sorted(glob.glob(f'{T}/p*.fit')) if open(f).read().strip())
open(f'{T}/fit.txt', 'w').write(fit + '\n')
bad = [l for l in fit.splitlines() if ' over=' in l and not l.split(' over=')[1].startswith(('0', '-'))]
drift = [l for l in fit.splitlines() if ' drift=' in l and int(l.split(' drift=')[1].split()[0]) > 12]
print(f'--- fit: {len(fit.splitlines())} pages with a type-size change (normal), {len(drift)} with drift>12, {len(bad)} OVERFLOWING')
for l in bad + drift[:20]:
    print('  ', l)
print(run(PY, f'{S}/merge.py', W, f'{T}/merged.pdf', *parts))
print(run(PY, f'{S}/outline.py', W, f'{T}/merged.pdf', OUT, *[p for p in parts if p.endswith('.pages')]))
if not os.path.exists(OUT):
    fail(f'outline.py wrote no {OUT}')
print(pages_of(OUT), 'pages,', os.path.getsize(OUT) // 1_000_000, 'MB ->', OUT)
if bad:
    sys.stdout.flush()
    print(f'--- FAILED: {len(bad)} pages overflow (see the fit report above; fix anchors, never cut text)', file=sys.stderr)
    sys.exit(3)
