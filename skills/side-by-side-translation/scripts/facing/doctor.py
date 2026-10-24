"""Check that this machine can run the facing-edition pipeline, and say how to fix what is missing.
usage: doctor.py [--lang deu,frk,lat] [--fix] [WORK]
Everything the pipeline does with the scan happens ON THIS MACHINE: page images (poppler), text lines (numpy),
OCR (the PDF's own text layer via pdftotext, or Tesseract), the English typesetting (headless Chrome) and the PDF
merge (pypdf).  Only the translation itself is done by Claude, which reads the page views and OCR lines the scripts
prepare.  No page or text is sent to any other service.  --fix installs the Python modules with pip (--user);
the command-line tools are printed as brew/apt commands for you to run.  Exit code = number of blocking problems."""
import sys, os, shutil, subprocess, json, platform

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = dict(zip(sys.argv[1:], sys.argv[2:] + ['']))
langs = (opt.get('--lang') or '').split(',') if '--lang' in sys.argv else []
W = args[0] if args else None
if W and os.path.exists(os.path.join(W, 'book.json')):
    j = json.load(open(os.path.join(W, 'book.json')))
    t = (j.get('ocr') or {}).get('tesseract')
    if t and t not in langs:
        langs.append(t)
langs = [l for l in langs if l] or ['deu']
FIX = '--fix' in sys.argv
mac = platform.system() == 'Darwin'
problems, warnings = [], []
PKG = 'brew install' if mac else 'sudo apt install'


def ok(label, detail=''):
    print(f'  ok   {label}' + (f'  ({detail})' if detail else ''))


def bad(label, fix, blocking=True):
    print(f'  {"MISSING" if blocking else "warn "}  {label}\n         fix: {fix}')
    (problems if blocking else warnings).append(label)


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 1, str(e)


print(f'facing-edition doctor — {platform.system()} {platform.release()}, python {sys.version.split()[0]} at {sys.executable}')
print('All scan processing and OCR run locally on this machine (see the docstring).')

# Python modules
missing = []
for mod, pip in (('numpy', 'numpy'), ('PIL', 'pillow'), ('pypdf', 'pypdf')):
    try:
        m = __import__(mod); ok(f'python module {mod}', getattr(m, '__version__', ''))
    except ImportError:
        missing.append(pip)
if missing:
    cmd = [sys.executable, '-m', 'pip', 'install', '--user', *missing]
    if FIX:
        print('  installing', *missing)
        rc, out = run(cmd)
        print('  ' + out.strip().splitlines()[-1] if out.strip() else '')
        if rc:
            bad('python modules ' + ' '.join(missing), ' '.join(cmd))
        else:
            ok('python modules installed: ' + ' '.join(missing))
    else:
        bad('python modules ' + ' '.join(missing), ' '.join(cmd) + '   (or: doctor.py --fix)')

# command-line tools
for tool, pkg, why in (('pdftoppm', 'poppler', 'renders page images'), ('pdftotext', 'poppler', 'reads the PDF text layer'),
                       ('pdfinfo', 'poppler', 'page counts'), ('tesseract', 'tesseract', 'local OCR')):
    p = shutil.which(tool)
    if p:
        ok(tool, p)
    else:
        bad(tool + f' ({why})', f'{PKG} {pkg}' + ('' if tool != 'tesseract' or mac else ' tesseract-ocr'))

# tesseract languages
if shutil.which('tesseract'):
    rc, out = run(['tesseract', '--list-langs'])
    have = set(out.split()[1:]) if rc == 0 else set()
    rc2, ver = run(['tesseract', '--version'])
    ok('tesseract version', ver.split('\n')[0].strip())
    for l in langs:
        if l in have or l.startswith('script/'):
            ok(f'tesseract language {l}')
        else:
            bad(f'tesseract language {l}', f'{PKG} tesseract-lang' if mac else f'sudo apt install tesseract-ocr-{l.replace("_", "-")}  '
                f'(frk = Fraktur: tesseract-ocr-script-frak or the frk.traineddata file in TESSDATA_PREFIX)')
    if 'frk' not in have and 'frk' not in langs:
        warnings.append('frk'); print('  note  Fraktur books need the "frk" language (tesseract-lang on Homebrew)')

# Chrome
here = os.path.dirname(os.path.abspath(__file__))
rc, out = run(['sh', f'{here}/render.sh', '--find'])
chrome = out.strip().splitlines()[-1] if out.strip() else ''
if chrome and os.path.exists(chrome.split('\n')[-1]):
    ok('Google Chrome / Chromium', chrome)
else:
    bad('Google Chrome or Chromium (typesets the English)', 'install Google Chrome, or set CHROME=/path/to/chrome')

# fonts for the facing layout (book.css: Hoefler Text → Iowan Old Style → Palatino → Georgia)
if mac:
    if any(os.path.exists(p) for p in ('/System/Library/Fonts/Supplemental/Hoefler Text.ttc', '/Library/Fonts/Hoefler Text.ttc')):
        ok('Hoefler Text (English type of the photocopy edition)')
    else:
        bad('Hoefler Text', 'book.css falls back to Iowan Old Style / Palatino / Georgia; type sizes adapt automatically', blocking=False)
else:
    rc, out = run(['fc-list'])
    fam = out.lower()
    found = next((f for f in ('hoefler', 'iowan', 'palatino', 'palladio', 'georgia', 'gelasio') if f in fam), None)
    if found:
        ok(f'serif face for the photocopy edition: {found}')
    else:
        bad('a serif face (Palatino/URW Palladio, Georgia or Gelasio)', 'sudo apt install fonts-urw-base35 fonts-crosextra-caladea  (fit.js adapts sizes)', blocking=False)

# agents
ag = os.path.expanduser('~/.claude/agents')
if all(os.path.exists(f'{ag}/facing-{n}.md') for n in ('translator', 'reviewer')):
    ok('lean agent definitions in ~/.claude/agents')
else:
    bad('facing-translator / facing-reviewer agents', 'new_book.py installs them (takes effect in the next session); until then use general-purpose agents', blocking=False)

print()
if problems:
    print(f'{len(problems)} blocking problem(s): ' + '; '.join(problems))
else:
    print('ready: everything the pipeline needs is installed.' + (f'  ({len(warnings)} note(s) above)' if warnings else ''))
sys.exit(len(problems))
