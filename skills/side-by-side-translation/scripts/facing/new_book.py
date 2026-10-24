"""Set up a book folder for a facing edition — one command instead of the old mkdir/cp/edit sequence.
usage: new_book.py SLUG SOURCE.pdf --layout facing|retype --kind ia|google|hathi|plain|images
                   [--lang deu|frk|lat|fra|ita|spa|…] [--root DIR] [--first N --last N] [--title "…"] [--author "…"]
                   [--out "…pdf"] [--prep [--flat]] [--no-agents]
  --layout facing   photocopy edition: the scan on the left, the English typeset beside it (like the Hegel
                    Encyclopaedia 1817 edition).
  --layout retype   clean-text edition: both columns typeset, the original pagination marked in the margins with a
                    red bar at each page break, footnotes at the page foot (like the Exner edition).
  --kind            source type for prep.py (ia = Internet Archive, google = Google Books, hathi = HathiTrust,
                    plain = any other/born-digital PDF, images = camera scans copied into work/raw/).
  --lang            tesseract language for pages without a usable text layer (frk = Fraktur, deu = Antiqua German…).
  --root            where book folders live (default ~/Desktop/claude-folder/_facing-pipeline; persistent, never the
                    session scratchpad, which gets wiped).
  --prep            also run prep.py and lines.py now (several minutes for a long book; may be run later).
Creates ROOT/SLUG/{scripts,engine,work}: scripts/ = this pipeline (copied, so the book keeps the version it was built
with), engine/ = the skill's landscape PDF engine (build_pdf.py + assets, needed by the retype layout), work/ =
book.json, DROP, AGENT.md / REVIEW.md / GLOSSARY.md / extra.css from the templates, src/orig.pdf.  Installs the lean
agent definitions into ~/.claude/agents (they take effect in the next session).  Runs doctor.py at the end."""
import sys, os, shutil, json, subprocess, re

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))          # …/side-by-side-translation
argv = sys.argv[1:]
flags = {'--prep', '--flat', '--no-agents'}
opt, pos, i = {}, [], 0
while i < len(argv):
    a = argv[i]
    if a in flags:
        opt[a] = True; i += 1
    elif a.startswith('--'):
        opt[a] = argv[i + 1] if i + 1 < len(argv) else ''; i += 2
    else:
        pos.append(a); i += 1
if len(pos) < 1 or '--layout' not in opt or opt['--layout'] not in ('facing', 'retype'):
    sys.exit(__doc__)
slug = re.sub(r'[^a-z0-9-]+', '-', pos[0].lower()).strip('-')
src = os.path.abspath(pos[1]) if len(pos) > 1 else None
layout = opt['--layout']
kind = opt.get('--kind', 'plain')
lang = opt.get('--lang', 'deu')
root = os.path.abspath(os.path.expanduser(opt.get('--root', '~/Desktop/claude-folder/_facing-pipeline')))
B = os.path.join(root, slug)
W = os.path.join(B, 'work')
if os.path.exists(os.path.join(W, 'book.json')):
    sys.exit(f'{B} already exists with a book.json — use it, or choose another slug')

# folders and scripts
for d in ('src', 'lines', 'zoom', 'en', 'notes', 'orn', 'ocr', 'scan', 'view', 'crops') + (('orig', 'retype') if layout == 'retype' else ()):
    os.makedirs(os.path.join(W, d), exist_ok=True)
if kind == 'images':
    os.makedirs(os.path.join(W, 'raw'), exist_ok=True)
shutil.copytree(HERE, os.path.join(B, 'scripts'), dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
eng = os.path.join(B, 'engine')
os.makedirs(os.path.join(eng, 'scripts'), exist_ok=True)
for f in os.listdir(os.path.join(SKILL, 'scripts')):
    if f.endswith('.py'):
        shutil.copy(os.path.join(SKILL, 'scripts', f), os.path.join(eng, 'scripts', f))
shutil.copytree(os.path.join(SKILL, 'assets'), os.path.join(eng, 'assets'), dirs_exist_ok=True)
if src:
    if kind == 'images':
        print('images: copy the page images into', os.path.join(W, 'raw'))
    else:
        shutil.copy(src, os.path.join(W, 'src', 'orig.pdf'))

# book.json from the template, with this book's values
T = os.path.join(SKILL, 'templates', 'facing')
j = json.load(open(os.path.join(T, 'book.json')))
j.pop('_comment', None)
j['layout'] = layout
j['first'] = int(opt.get('--first', 1)); j['last'] = int(opt.get('--last', 9999))
j['folio'] = {'format': '{n}', 'ranges': [{'from': j['first'], 'to': j['last'], 'offset': 0}], 'none': []}
j['marks'] = []; j['outline'] = []
j['ocr'] = {'pdf': 'src/orig.pdf', 'pdf_offset': 0, 'align': 'page', 'tesseract': lang}
title, author = opt.get('--title', ''), opt.get('--author', '')
j['meta'] = {'title': title, 'author': author}
j['out'] = opt.get('--out') or os.path.join(os.path.dirname(root), f'{slug} ({"DE" if lang in ("deu", "frk") else "XX"}-EN {"facing" if layout == "facing" else "clean text"}).pdf')
if layout == 'retype':
    j['retype'] = {'levels': {'h1': 1, 'h2': 2, 'h3': 2, 'h4': 3}, 'note_marks': '*', 'lang': ['de' if lang in ('deu', 'frk') else 'xx', 'en'],
                   'author': author, 'work': f'<i>{title}</i>' if title else '', 'edition': '', 'keep_note_numbers': False,
                   'build_flags': []}
j['_comment'] = (f'{slug}: {layout} layout ({"photocopy: scan left, English right" if layout == "facing" else "clean text: both columns typeset, margin pagination"}); '
                 f'source kind {kind}; edit folio.ranges (scan -> printed page offsets, roman, prefix), folio.none, marks, outline, out, meta'
                 + (', retype.*' if layout == 'retype' else '') + '. Unset keys take the defaults in scripts/book.py.')
json.dump(j, open(os.path.join(W, 'book.json'), 'w'), indent=1, ensure_ascii=False)
open(os.path.join(W, 'DROP'), 'a').close()

# briefs from the templates
for f in ('AGENT.md', 'REVIEW.md', 'GLOSSARY.md', 'extra.css'):
    s = open(os.path.join(T, f)).read()
    if f == 'AGENT.md' and layout == 'facing':        # the retypeset section applies only to clean-text editions
        s = re.sub(r'\n## Retypeset editions only.*?(?=\n## Finish)', '\n', s, flags=re.S)
    if f == 'AGENT.md' and layout == 'retype':
        s = s.replace(' (book.json has a "retype" section; delete this section otherwise)', '')
    s = s.replace('{{WORK}}', W)
    open(os.path.join(W, f), 'w').write(s)

# lean agents
if not opt.get('--no-agents'):
    ag = os.path.expanduser('~/.claude/agents')
    os.makedirs(ag, exist_ok=True)
    for f in ('facing-translator.md', 'facing-reviewer.md'):
        d = os.path.join(ag, f)
        if not os.path.exists(d):
            shutil.copy(os.path.join(SKILL, 'agents', f), d); print('installed agent', f, '(active from the next session)')

print(f'book folder: {B}\n  layout: {layout}   source kind: {kind}   tesseract: {lang}\n  edit {W}/book.json (first/last, folio ranges, out), then:')
PY = os.path.join(B, 'scripts', 'py')
print(f'  cd {B} && scripts/py prep.py work {kind}{" --flat" if opt.get("--flat") else ""} && scripts/py lines.py work > work/lines.log')
print(f'  scripts/py bundle.py work s020 s021      # smoke test')
if opt.get('--prep') and src:
    print('running prep.py and lines.py …', flush=True)
    subprocess.run([PY, 'prep.py', 'work', kind] + (['--flat'] if opt.get('--flat') else []), cwd=B, check=True)
    with open(os.path.join(W, 'lines.log'), 'w') as fh:
        subprocess.run([PY, 'lines.py', 'work'], cwd=B, stdout=fh, check=True)
    print('prep done:', len(os.listdir(os.path.join(W, 'scan'))), 'scan pages; lines.log written')
subprocess.run([PY, 'doctor.py', '--lang', lang, W], cwd=B)
