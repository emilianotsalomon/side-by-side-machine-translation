"""Clean-text edition ("Exner / Trendelenburg style"): original and English both typeset, paragraph rows aligned,
the original pagination marked at the exact word where each page begins (number in the outer margin, thin red bar
in the text), the author's footnotes at the foot of the page, chapter titles as headings opening a new page.
Input: the per-page fragments of the facing pipeline — WORK/orig/sPPP.html (the corrected original) and
WORK/en/sPPP.html, written with the SAME blocks in the same order.  Output: WORK/retype/orig.md + trans.md, then
build_pdf.py (the skill's landscape engine, copied into BOOK/engine/ by new_book.py) renders the PDF.
usage: retype.py WORK [OUT.pdf] [--pages 16-22,69-72 | s016-s022] [--check] [--no-pdf] [-- extra build_pdf flags]
book.json "retype": {"levels": {"h1": 1, "h2": 1, "h3": 2, "h4": 3}, "note_marks": "*", "lang": ["de", "en"],
                     "author": "…", "work": "<i>…</i> (1841)", "edition": "the first edition of 1841",
                     "keep_note_numbers": false, "footnote": "…", "build_flags": ["--kind", "0=orn"], "engine": "…"}
Display classes in the fragments (same class in orig and en): ctr centred line(s) · ctrp centred + new page ·
epi epigraph · epa epigraph attribution · syn synopsis line · ver / v verse · quo block quotation · sep section rule.
Folio ranges may carry "prefix": "I." → margin numbers [I.23] (two Hefte in one volume)."""
import sys, os, re, html, json, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

argv = sys.argv[1:]
extra = argv[argv.index('--') + 1:] if '--' in argv else []
argv = argv[:argv.index('--')] if '--' in argv else argv
args = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] != '--pages')]
W = os.path.abspath(args[0])
cfg = book.load(W)
R = cfg.get('retype', {})
OUT = os.path.abspath(args[1]) if len(args) > 1 else (os.path.abspath(os.path.expanduser(cfg['out'])) if cfg.get('out') else None)
LEVELS = {'h1': 1, 'h2': 1, 'h3': 2, 'h4': 3, **R.get('levels', {})}
KINDS = {'ctr': 'orn', 'ctrp': 'ornp', 'epi': 'epi', 'epa': 'epa', 'syn': 'syn', 'ver': 'ver', 'v': 'ver',
         'quo': 'quo', 'sep': 'orn'}
SKIP = re.compile(r'^(rh|sig|sigf|cw|orn|fig)\b')
BLOCK = re.compile(r'<(p|h[1-6]|div|hr)\b([^>]*)>(.*?)</\1>|<hr\b[^>]*>', re.S)


def blocks(path):
    """[(kind, cls, inner)] for one fragment, page furniture removed"""
    s = re.sub(r'<!--.*?-->', '', open(path).read(), flags=re.S)
    out = []
    for m in BLOCK.finditer(s):
        if m.group(1) is None or m.group(1) == 'hr':
            continue
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        cls = (re.search(r'class="([^"]*)"', attrs) or [None, ''])[1]
        if SKIP.match(cls):
            continue
        if tag.startswith('h'):
            out.append(('h', tag, inner))
        elif cls.split()[:1] == ['cols']:     # two-column block (Greek beside its version): quotation, then the version
            sp = re.findall(r'<span[^>]*>(.*?)</span>', inner, re.S)
            out.append(('p', 'quo', sp[0] if sp else inner))
            out += [('p', 'par', x) for x in sp[1:]]
        elif cls.startswith('note'):          # a new note starts with its mark; anything else continues one
            marked = re.match(r'\s*(<sup>|\*+\)|\d{1,3}\s?[a-c]?\)|[*†‡]|\(\d{1,3}\))', inner)
            out.append(('note' if marked and 'cont' not in cls.split() else 'ncont', cls, inner))
        else:
            out.append(('p', cls, inner))
    return out


def inline(h):
    """fragment HTML -> Markdown-ish text: <em> -> *…*, cues kept as ⟨CUE⟩, other tags dropped"""
    h = re.sub(r'<br\s*/?>', ' | ', h)          # printed line breaks (schemata, verse) -> ' | ', never at a line start
    h = re.sub(r'</span>\s*<span[^>]*>', ' ', h)       # table/formula cells
    h = re.sub(r'<sup>[^<]*</sup>', '⟨CUE⟩', h)
    h = h.replace('*', '∗')                     # literal asterisks (note marks) must not read as italics
    h = re.sub(r'</?(em|i)>', '*', h)
    h = html.unescape(re.sub(r'<[^>]+>', '', h))
    h = re.sub(r'\*(\s*)\*', r'\1', h)          # adjacent emphasis spans merge
    return re.sub(r'\s+', ' ', h).strip()


def note_text(h):
    h = inline(h)
    return re.sub(r'^(⟨CUE⟩|∗+\)|\d+\s?[a-c]?\)|\(\d+\)|[∗†‡]+)\s*', '', h)


def page_set(spec):
    """'16-22,69-72' or 's016-s022' or '16,s018' -> set of scan numbers"""
    keep = set()
    for r in spec.split(','):
        x, _, y = r.partition('-')
        x, y = x.strip().lstrip('s'), y.strip().lstrip('s')
        keep |= set(range(int(x), int(y or x) + 1))
    return keep


pages = [p for p in book.pages(cfg) if os.path.exists(f'{W}/en/{p}.html')]
if '--pages' in argv:                               # a pilot or one volume
    keep = page_set(argv[argv.index('--pages') + 1])
    pages = [p for p in pages if int(p[1:]) in keep]
problems = []
for p in pages:
    if not os.path.exists(f'{W}/orig/{p}.html'):
        problems.append(f'{p}: no orig/{p}.html'); continue
    a, b = blocks(f'{W}/orig/{p}.html'), blocks(f'{W}/en/{p}.html')
    if [x[0] for x in a] != [x[0] for x in b]:
        problems.append(f'{p}: block structure differs  orig {"".join(k[0] for k, *_ in a)}  en {"".join(k[0] for k, *_ in b)}')
    for side, bl in (('orig', a), ('en', b)):
        cues = sum(x[2].count('<sup') for x in bl if x[0] in ('p', 'h'))
        notes = sum(1 for x in bl if x[0] == 'note')
        if cues != notes:
            problems.append(f'{p} {side}: {cues} note cue(s) but {notes} note(s)')
if problems or '--check' in argv:
    print('\n'.join(problems) or 'retype check: ok')
    if problems:
        sys.exit(1)
    if '--check' in argv:
        sys.exit()


def prefix(scan):
    return next((r.get('prefix', '') for r in cfg['folio']['ranges'] if r['from'] <= scan <= r['to']), '')


# rows: each row = {'kind': 'h'|'p', 'level', 'text': [orig, en], 'notes': [[id, orig, en, printed label], ...]}
rows, k = [], 900                                  # note ids 901… never collide with enumerations "1)" in the text
pending = []                                       # cue ids, matched in order to the notes (a note may be printed a page after its cue)
for p in pages:
    scan = int(p[1:])
    n = book.printed(cfg, scan)
    mark = f'[{prefix(scan)}{n.lower() if n and not n.isdigit() else n}] ' if n else ''
    a, b = blocks(f'{W}/orig/{p}.html'), blocks(f'{W}/en/{p}.html')
    first_text = True
    for (ka, ca, ha), (kb, cb, hb) in zip(a, b):
        ta, tb = inline(ha), inline(hb)
        if ka in ('p', 'h'):
            ids = []
            while '⟨CUE⟩' in ta or '⟨CUE⟩' in tb:
                k += 1; ids.append(k)
                ta, tb = ta.replace('⟨CUE⟩', f'[^{k}]', 1), tb.replace('⟨CUE⟩', f'[^{k}]', 1)
            pending += ids
            cls0 = ca.split()[0] if ca.split() else ''
            if ka == 'p' and cls0 == 'sep':         # printed section rule -> centred dash ornament
                ta = tb = '———'
            cont = first_text and ka == 'p' and not ca.split() and rows and rows[-1]['kind'] == 'p'
            if first_text and mark:
                ta, tb = mark + ta, mark + tb
            if ka == 'h' and rows and rows[-1]['kind'] == 'h' and not rows[-1]['notes'] and rows[-1].get('tag') == ca:   # "I." + "Title" = one heading
                rows[-1]['text'] = [rows[-1]['text'][0] + ' ' + ta, rows[-1]['text'][1] + ' ' + tb]
                rows[-1]['level'] = min(rows[-1]['level'], LEVELS.get(ca, 1)); rows[-1]['cues'] += ids
                first_text = False
                continue
            if cont:                                # paragraph running over from the previous page
                rows[-1]['text'] = [rows[-1]['text'][0] + ' ' + ta, rows[-1]['text'][1] + ' ' + tb]
                rows[-1]['cues'] += ids
            else:
                if ka == 'p' and cls0 in KINDS:     # display kinds -> engine marker (build_pdf.py ⟪kind⟫)
                    ta, tb = f'⟪{KINDS[cls0]}⟫ ' + ta, f'⟪{KINDS[cls0]}⟫ ' + tb
                rows.append({'kind': ka, 'tag': ca, 'level': LEVELS.get(ca, 1) if ka == 'h' else 0, 'text': [ta, tb],
                             'notes': [], 'cues': list(ids)})
            first_text = False
        elif ka == 'note':
            nid = pending.pop(0) if pending else None
            host = next((r for r in reversed(rows) if nid in r.get('cues', [])), rows[-1] if rows else None)
            if host is not None:
                lab = re.match(r'\s*(?:<sup>)?\s*(\d{1,3}\s?[a-c]?|\*+)\s*\)', ha)
                host['notes'].append([nid, note_text(ha), note_text(hb), lab.group(1) if lab else '?'])
        elif ka == 'ncont':                         # note continued from the previous page
            last = next((r for r in reversed(rows) if r['notes']), None)
            if last:
                last['notes'][-1][1] += ' ' + note_text(ha)
                last['notes'][-1][2] += ' ' + note_text(hb)


def guard(t):
    """a body paragraph that opens like a note ("1) …", "(2) …", "3 …", "∗) …") would be taken for one by the
    engine: a word joiner after the number keeps it body text and is invisible in print"""
    return re.sub(r'^((?:\[[^\]]+\]\s*)?(?:⟪\w+⟫\s*)?\(?)(\d{1,3}|[∗†‡]+)(?=\)|\s)', '\\1\\2⁠', t)


for r in rows:
    if r['kind'] == 'p':
        r['text'] = [guard(t) for t in r['text']]
os.makedirs(f'{W}/retype', exist_ok=True)
for side, name in ((0, 'orig.md'), (1, 'trans.md')):
    out = []
    for r in rows:
        t = r['text'][side]
        out.append(('#' * r['level'] + ' ' + t) if r['kind'] == 'h' else t)
        for nid, no, ne, *_ in r['notes']:
            out.append(f'[^{nid}]: {(no, ne)[side]}' if nid else (no, ne)[side])
    open(f'{W}/retype/{name}', 'w').write('\n\n'.join(out) + '\n')
json.dump([n[3] for r in rows for n in r['notes'] if n[0]], open(f'{W}/retype/labels.json', 'w'))
print(len(rows), 'rows,', k - 900, 'notes ->', f'{W}/retype/orig.md, trans.md')
if '--no-pdf' in argv or not OUT:
    sys.exit()

# the landscape engine: BOOK/engine/scripts/build_pdf.py (copied by new_book.py), else the skill install
here = os.path.dirname(os.path.realpath(__file__))
cands = [R.get('engine', ''), os.path.join(os.path.dirname(W), 'engine', 'scripts', 'build_pdf.py'),
         os.path.join(os.path.dirname(here), 'build_pdf.py'),
         os.path.join(os.environ.get('SBS_SKILL_BASE', ''), 'scripts', 'build_pdf.py')]
cands += sorted(glob.glob(os.path.expanduser('~/.claude/skills/side-by-side-translation/scripts/build_pdf.py'))
                + glob.glob(os.path.expanduser('~/.claude/plugins/*/*/skills/side-by-side-translation/scripts/build_pdf.py'))
                + glob.glob(os.path.expanduser('~/.claude/plugins/*/skills/side-by-side-translation/scripts/build_pdf.py'))
                + glob.glob(os.path.expanduser('~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills/side-by-side-translation/scripts/build_pdf.py')),
                key=os.path.getmtime, reverse=True)
engine = next((c for c in cands if c and os.path.exists(c)), None)
if not engine:
    sys.exit('build_pdf.py not found: run new_book.py (it copies the engine into BOOK/engine/) or set book.json retype.engine')
lang = R.get('lang', ['de', 'en'])
cmd = [sys.executable, engine, f'{W}/retype/orig.md', f'{W}/retype/trans.md',
       '--lang', *lang, '--md-italics', '--no-propagate-markers', '--chapter-breaks', '--page-notes', '--margin-folios',
       '--break-bars', '--note-marks', R.get('note_marks', '{n}'), '-o', OUT]
for key in ('author', 'work', 'edition', 'running_head', 'footnote'):
    if R.get(key):
        cmd += [f'--{key.replace("_", "-")}', R[key]]
if R.get('keep_note_numbers'):
    cmd += ['--note-labels', f'{W}/retype/labels.json']
cmd += list(R.get('build_flags', [])) + extra
print('engine:', engine)
sys.exit(subprocess.run(cmd).returncode)
