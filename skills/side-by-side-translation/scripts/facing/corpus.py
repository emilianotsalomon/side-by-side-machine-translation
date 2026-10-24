"""Export a finished edition as ONE Markdown file for the team's knowledge base (corpus).
usage:
  corpus.py book BOOKDIR  -o CORPUS [--title T --title-en T --author A --year Y --lang de] [--slug name]
  corpus.py pdf  FILE.pdf -o CORPUS  --title T --author A --year Y --lang de [--title-en T] [--slug name]
                 [--first N --last N] [--both]      (--both: the left half is typeset text too, not a scan)
  corpus.py text FILE.(pdf|epub|md|txt) -o CORPUS --title … --author … --year … --lang de [--ocr deu|frk]
                 (an ORIGINAL with no translation; --ocr runs Tesseract locally on pages without a text layer)
  corpus.py chunks DIR -o CORPUS …                 (a chunk_tools translation: cNN.src.md + cNN.en.md, [[n]] tags)
  corpus.py html FILE.html|DIR -o CORPUS/sub --author … [--collection "…"] [--prefix slugprefix]
                 (Tufte-style HTML readers: folios, sidenotes, dialogue, headings; one corpus file per HTML file)
  corpus.py index CORPUS                           (writes CORPUS/README.md from the files' headers; sub-folders too)

The file: a YAML header (title, author, year, languages, where the text comes from, how far it has been checked),
then the text. Page starts are marked `[p. 79]` (printed page numbers, as the folio reads). The ORIGINAL stands in
quoted blocks (`> …`), the ENGLISH in plain paragraphs, so the two are told apart at a glance and either can be
filtered out with one regex. Headings become Markdown headings (original — English). Emphasis as printed (*…*),
footnote cues as <sup>, notes after the paragraph that carries them. Nothing is edited: the corpus is generated from
the page files in BOOKDIR/work (en/, orig/, ocr/), which stay the source of truth — except for the PDF-only books
(mode pdf), where the English is recovered from the PDF and the corpus file itself is the source."""
import sys, os, re, html, json, glob, subprocess, datetime

args = [a for a in sys.argv[1:]]
if len(args) < 2:
    sys.exit(__doc__)
MODE, SRC = args[0], args[1]
opt, i = {}, 2
while i < len(args):
    if args[i] in ('--both',):
        opt[args[i]] = True; i += 1
    elif args[i].startswith('--') or args[i] == '-o':
        opt[args[i]] = args[i + 1]; i += 2
    else:
        i += 1
TODAY = datetime.date.today().isoformat()
SKIP = re.compile(r'^(rh|sig|sigf|cw|orn|fig|foot)\b')
BLOCK = re.compile(r'<(p|h[1-6]|div)\b([^>]*)>(.*?)</\1>', re.S)


# ---------- fragment HTML -> Markdown ----------
def inline(h):
    h = re.sub(r'<br\s*/?>', ' / ', h)
    h = re.sub(r'</span>\s*<span[^>]*>', ' ', h)
    h = re.sub(r'<sup>(.*?)</sup>', lambda m: '<sup>' + re.sub(r'<[^>]+>', '', m.group(1)) + '</sup>', h)
    h = h.replace('*', '∗')
    h = re.sub(r'<(em|i)>\s*', '*', h); h = re.sub(r'\s*</(em|i)>', '*', h)
    h = re.sub(r'<(?!/?sup>)[^>]+>', '', h)
    h = html.unescape(h)
    h = re.sub(r'\*(\s*)\*', r'\1', h)
    return re.sub(r'\s+', ' ', h).strip()


def blocks(path):
    """[(kind, cls, text)]  kind: h1..h4 | p | note | mn"""
    s = re.sub(r'<!--.*?-->', '', open(path).read(), flags=re.S)
    out = []
    for m in BLOCK.finditer(s):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        cls = (re.search(r'class="([^"]*)"', attrs) or [None, ''])[1]
        c0 = cls.split()[0] if cls.split() else ''
        if SKIP.match(cls):
            continue
        t = inline(inner)
        if not t:
            continue
        if tag.startswith('h'):
            out.append((tag, cls, t))
        elif c0 in ('note', 'fn'):
            out.append(('note', cls, t))
        elif c0 == 'mn':
            out.append(('mn', cls, t))
        elif c0 in ('toc', 'toch'):
            out.append(('p', cls, re.sub(r'\s*/\s*', ' … ', t)))
        else:
            out.append(('p', cls, t))
    return out


def folio(path):
    m = re.search(r'<p class="rh[^"]*"[^>]*>(.*?)</p>', open(path).read(), re.S)
    if not m:
        return None
    t = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))
    t = re.sub(r'[—–\-\[\]().]', ' ', t)
    cands = [w for w in t.split() if re.fullmatch(r'\d{1,4}|[ivxlcIVXLC]{1,7}', w)]
    return cands[-1] if cands else None


def quote(t):
    return '\n'.join('> ' + l for l in t.split('\n'))


def ocr_text(W, p):
    for f in (f'{W}/ocr/{p}.txt', f'{W}/ocr/b_{p}.txt'):
        if os.path.exists(f):
            s = open(f, errors='replace').read()
            break
    else:
        f = f'{W}/ocr/{p}.tsv'
        if os.path.exists(f):
            rows = [r.split('\t') for r in open(f).read().splitlines() if r]
            rows.sort(key=lambda r: (round(float(r[1]) / 20), float(r[0])))
            s = ' '.join(r[4] for r in rows if len(r) > 4)
        else:
            src = glob.glob(f'{W}/src/*.pdf')
            if not src:
                return None
            n = int(p[1:])
            s = subprocess.run(['pdftotext', '-f', str(n), '-l', str(n), src[0], '-'], capture_output=True, text=True).stdout
            if len(s.strip()) < 40:
                return None
    s = re.sub(r'^\s*[-—–\s]*\(?[\divxlcIVXLC]{1,6}\)?[-—–\s]*\n', '', s)     # folio line at the top
    s = re.sub(r'(\w)\s?[-¬‐=]\s*\n(?=\s*[a-zäöüß])', r'\1', s)                # line-end hyphenation
    s = re.sub(r'\s+', ' ', s)                                               # OCR paragraphing is unreliable: one block
    s = re.sub(r'\s+([,.;:!?)])', r'\1', s).strip()
    return s if len(s) > 20 else None


# ---------- mode book ----------
def mode_book():
    B = os.path.abspath(SRC); W = f'{B}/work'
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import book
    cfg = book.load(W)
    pages = [p for p in book.pages(cfg) if os.path.exists(f'{W}/en/{p}.html')]
    has_orig = os.path.isdir(f'{W}/orig') and len(glob.glob(f'{W}/orig/s*.html')) >= len(pages) * 0.9
    meta = cfg.get('meta', {}); R = cfg.get('retype', {})
    title = opt.get('--title') or re.sub(r'<[^>]+>', '', R.get('work', '')) or meta.get('title', '') or os.path.basename(B)
    author = opt.get('--author') or R.get('author') or meta.get('author', '')
    slug = opt.get('--slug') or os.path.basename(B)
    lang = opt.get('--lang') or (R.get('lang') or ['de'])[0]
    out_lines = []
    add = out_lines.append
    npages = 0
    if has_orig:                                           # paragraph pairs, markers inline (clean-text editions)
        rows, carry = [], None
        for p in pages:
            a, b = blocks(f'{W}/orig/{p}.html'), blocks(f'{W}/en/{p}.html')
            if [x[0] for x in a] != [x[0] for x in b]:
                print(f'  {p}: block structure differs — paired by position', file=sys.stderr)
            n = folio(f'{W}/en/{p}.html')
            pre = next((r.get('prefix', '') for r in cfg['folio']['ranges'] if r['from'] <= int(p[1:]) <= r['to']), '')
            mark = f'[p. {pre}{n}]' if n else f'[scan {int(p[1:])}]'
            first = True
            notes = []
            for (ka, ca, ta), (kb, cb, tb) in zip(a, b):
                if ka == 'note':
                    notes.append((ta, tb)); continue
                cont = first and ka == 'p' and not ca.split() and rows and rows[-1][0] == 'p'
                if first:
                    if ka.startswith('h'):
                        rows.append(['mark', mark, mark, []])
                    else:
                        ta, tb = f'{mark} {ta}', f'{mark} {tb}'
                    first = False
                if cont:
                    rows[-1][1] += ' ' + ta; rows[-1][2] += ' ' + tb
                else:
                    rows.append([ka, ta, tb, []])
            if first:                                       # page without body text
                rows.append(['p', mark, mark, []])
            if rows:
                rows[-1][3] += notes
            npages += 1
        for k, ta, tb, notes in rows:
            if k == 'mark':
                add(ta); add(''); continue
            if k.startswith('h'):
                lvl = min(6, int(k[1]) + 1)
                add('#' * lvl + ' ' + (f'{ta} — {tb}' if ta != tb else ta)); add('')
            else:
                add(quote(ta)); add(''); add(tb); add('')
            for na, nb in notes:
                add(quote(na)); add(''); add(nb); add('')
        otext = 'corrected transcription of the print (by the translators, checked by the reviewers)'
    else:                                                  # page pairs: OCR page, then the English of that page
        nocr = 0
        for p in pages:
            n = folio(f'{W}/en/{p}.html')
            add(f'[p. {n}]' if n else f'[scan {int(p[1:])}]'); add('')
            o = ocr_text(W, p)
            if o:
                nocr += 1; add(quote(o)); add('')
            body, notes, margins = [], [], []
            for k, c, t in blocks(f'{W}/en/{p}.html'):
                if k == 'note':
                    notes.append(t)
                elif k == 'mn':
                    margins.append(t)
                elif k.startswith('h'):
                    body.append('#' * min(6, int(k[1]) + 1) + ' ' + t)
                else:
                    body.append(t)
            for m in margins:
                body.insert(0, f'[margin: {m}]')
            for t in body + notes:
                add(t); add('')
            npages += 1
        has_ocr = glob.glob(f'{W}/ocr/*.t*')
        otext = ('OCR of the scan, uncorrected (the scan in the PDF edition is the authority)' if nocr else
                 'not in this file (scan only — see the PDF edition)')
        if nocr and not has_ocr:
            otext = "the source PDF's own text (born-digital)"
    head = {'title': title, 'title_en': opt.get('--title-en', ''), 'author': author, 'year': opt.get('--year', ''),
            'original_language': lang, 'translation_language': 'en',
            'edition_layout': 'clean text (both columns typeset)' if cfg.get('layout') == 'retype' or has_orig else 'photocopy (scan beside the English)',
            'source': f'page files of _facing-pipeline/{os.path.basename(B)} (generated — edit the page files, not this file)',
            'original_text': otext,
            'translation': 'machine-made (Claude), reviewed against the original by Claude; no human review',
            'pages': npages, 'generated': f'{TODAY} by corpus.py'}
    write(slug, head, out_lines)


# ---------- mode pdf ----------
def pdf_half(f, p, x, w, h):
    return subprocess.run(['pdftotext', '-f', str(p), '-l', str(p), '-layout', '-x', str(x), '-y', '0', '-W', str(w), '-H', str(h), f, '-'],
                          capture_output=True, text=True).stdout


def parse_half(txt):
    """layout text of one half -> (folio, [paragraphs], [notes])"""
    lines = txt.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    fol = None
    if lines:
        h = lines[0].strip()
        capsy = len(re.findall(r'[A-Z] [A-Z]', h)) > 2 or (h.isupper() and len(h) < 70)
        m = re.match(r'^(\d{1,4})\b(.*)$', h) or re.match(r'^(.*?)\b(\d{1,4})$', h)
        num = (m.group(1) if m and m.group(1).isdigit() else m.group(2)) if m else None
        rest = (h.replace(num, '', 1) if num else h).strip(' .')
        gap = re.match(r'^\d{1,4}\s{3,}\S', h) or re.search(r'\S\s{3,}\d{1,4}$', h)     # layout mode: folio set apart from the head
        if num and (gap or (not re.search(r'[,;:]', rest) and (capsy or len(rest) < 40))) and not re.search(r'\b(1[5-9]|20)\d\d\b', h):
            fol = num; lines.pop(0)
        elif re.fullmatch(r'[ivxlc]{1,7}', h.lower()) or re.fullmatch(r'[ivxlc]{2,7}\s+[A-Z .’\'\-–—]+|[A-Z .’\'\-–—]+\s+[ivxlc]{2,7}', h):
            fol = re.search(r'\b([ivxlc]{1,7})\b', h.lower()).group(1); lines.pop(0)
        elif capsy and re.fullmatch(r'[A-Z .,’\'\-–—]+', h):
            lines.pop(0)
    inds = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    base = min(inds) if inds else 0
    paras, notes, cur = [], [], ''
    for l in lines:
        if not l.strip():
            if cur:
                paras.append(cur); cur = ''
            continue
        ind = len(l) - len(l.lstrip()) - base
        t = l.strip()
        isnote = re.match(r'^\(\d{1,3}\)\s|^\d{1,3}\)\s|^\*+\)?\s|^[†‡]\s', t) and ind <= 4
        if isnote and cur:
            paras.append(cur); cur = ''
        if (ind >= 2 or isnote) and cur:
            paras.append(cur); cur = ''
        if cur.endswith(('‐', '­')):
            cur = cur[:-1] + t
        elif cur.endswith('-') and t[:1].islower():
            cur = cur + t
        else:
            cur = (cur + ' ' + t).strip()
    if cur:
        paras.append(cur)
    body = [p for p in paras if not re.match(r'^\(\d{1,3}\)\s|^\d{1,3}\)\s|^\*+\)?\s|^[†‡]\s', p)]
    notes = [p for p in paras if p not in body]
    return fol, body, notes


def mode_pdf():
    f = os.path.abspath(SRC)
    info = subprocess.run(['pdfinfo', f], capture_output=True, text=True).stdout
    n = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    m = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info)
    Wd, Ht = float(m.group(1)), float(m.group(2))
    first, last = int(opt.get('--first', 1)), int(opt.get('--last', n))
    both = opt.get('--both', False)
    out, npages, nleft = [], 0, 0
    add = out.append
    for p in range(first, last + 1):
        right = pdf_half(f, p, int(Wd / 2), int(Wd / 2) + 2, int(Ht) + 2)
        left = pdf_half(f, p, 0, int(Wd / 2), int(Ht) + 2)
        folR, bodyR, notesR = parse_half(right)
        folL, bodyL, notesL = parse_half(left)
        if not bodyR and not bodyL:
            continue
        fol = folR or folL
        add(f'[p. {fol}]' if fol else f'[PDF {p}]'); add('')
        if both and bodyL:
            for a, b in zip(bodyL + notesL, bodyR + notesR):
                add(quote(a)); add(''); add(b); add('')
            extra = (bodyR + notesR)[len(bodyL + notesL):]
            for b in extra:
                add(b); add('')
            nleft += 1
        else:
            if len(' '.join(bodyL)) > 200:
                add(quote(' '.join(bodyL + notesL))); add(''); nleft += 1
            for b in bodyR + notesR:
                add(b); add('')
        npages += 1
    otext = ('typeset text of the edition' if both else
             'OCR text layer of the scan, uncorrected' if nleft > npages * 0.5 else
             'not in this file (scan only — see the PDF edition)')
    head = {'title': opt.get('--title', os.path.basename(f)), 'title_en': opt.get('--title-en', ''), 'author': opt.get('--author', ''),
            'year': opt.get('--year', ''), 'original_language': opt.get('--lang', ''), 'translation_language': 'en',
            'edition_layout': 'clean text (both columns typeset)' if both else 'photocopy (scan beside the English)',
            'source': f'recovered from the PDF ‘{os.path.basename(f)}’ (the page files were not kept) — THIS FILE IS THE SOURCE, corrections go here',
            'original_text': otext,
            'translation': 'machine-made (Claude), reviewed against the original by Claude; no human review',
            'pages': npages, 'generated': f'{TODAY} by corpus.py'}
    write(opt.get('--slug') or re.sub(r'[^a-z0-9]+', '-', os.path.basename(f).lower()).strip('-')[:40], head, out)


def write(slug, head, body_lines):
    C = os.path.abspath(opt.get('-o', 'corpus')); os.makedirs(C, exist_ok=True)
    path = f'{C}/{slug}.md'
    fm = '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) and (":" in v or v.startswith(("[", "*"))) else v}' for k, v in head.items())
    t = f"# {head['author']}, *{head['title']}*" + (f" ({head['year']})" if head['year'] else '') + (f" — *{head['title_en']}*" if head['title_en'] else '')
    conv = ('Conventions: `[p. N]` marks where a printed page begins (its folio as printed); quoted blocks (`> …`) are the '
            'original, plain paragraphs the English; `*…*` is emphasis as printed; `<sup>…</sup>` a footnote cue, the note '
            'following its paragraph. Generated file — see the header for where corrections belong.')
    sep = '\n' if '' in body_lines else '\n\n'          # lists built without blank entries: one paragraph per item
    open(path, 'w').write(f'---\n{fm}\n---\n\n{t}\n\n{conv}\n\n' + sep.join(body_lines).rstrip() + '\n')
    print(f'{path}: {head["pages"]} pages, {os.path.getsize(path) // 1000} KB')


def mode_index():
    C = os.path.abspath(SRC)
    rows = []
    for f in sorted(glob.glob(f'{C}/*.md')) + sorted(glob.glob(f'{C}/*/*.md'), key=lambda x: (os.path.dirname(x), re.search(r'^order: (.*)$', open(x).read(), re.M).group(1) if re.search(r'^order: (.*)$', open(x).read(), re.M) else '', x)):
        if os.path.basename(f) in ('README.md', 'PROJECT-INSTRUCTIONS.md') or '/glossaries/' in f or '/notes/' in f:
            continue
        s = open(f).read()
        m = re.match(r'---\n(.*?)\n---', s, re.S)
        h = dict(re.findall(r'^(\w+): (.*)$', m.group(1), re.M)) if m else {}
        g = lambda k: h.get(k, '').strip('"')
        langs = g("original_language") + ('→en' if g("translation_language") != 'none' else ' (original only)')
        rel = os.path.relpath(f, C)
        rows.append(f'| {g("author")} | *{g("title")}* ({g("year")}){(" · " + g("collection")) if g("collection") else ""} | {langs} | {g("pages")} | {g("edition_layout").split(" (")[0]} | {g("original_text").split(" (")[0]} | [{rel}]({rel}) |')
    open(f'{C}/README.md', 'w').write('# Corpus — facing editions\n\nOne Markdown file per edition: original in quoted blocks, English in plain paragraphs, `[p. N]` at every printed page start. '
                                      'All translations are machine-made (Claude) and reviewed against the original by Claude, not by a human translator, unless the file header says otherwise. '
                                      'Files generated from page files are regenerated by `corpus.py`; corrections go into the page files. Files recovered from a PDF are themselves the source.\n\n'
                                      '| author | work | languages | pages | layout | original text | file |\n|---|---|---|---|---|---|---|\n' + '\n'.join(rows) + '\n\n'
                                      f'Glossaries and translation policies per book: `glossaries/`. Generated {TODAY}.\n')
    print(f'{C}/README.md: {len(rows)} editions')


# ---------- mode text: an original with no translation (pdf / epub / md / txt) ----------
def norm_markers(t):
    t = re.sub(r'⟦([^⟧]+)⟧', r'[p. \1]', t)                       # Trendelenburg-style markers
    t = re.sub(r'^\[pdf (\d+)\]$', r'[PDF \1]', t, flags=re.M)    # ocr-tool markers (PDF page, not printed)
    t = re.sub(r'^\**\[(\d{1,4}|[ivxlc]{1,6})\]\**$', r'[p. \1]', t, flags=re.M)   # standalone [n] page blocks
    return t


def md_paras(text):
    """Markdown/plain text -> list of paragraphs; headings kept, [[n]] chunk tags dropped, page blocks standalone"""
    text = norm_markers(text.replace('\r', ''))
    text = re.sub(r'^\[\[\d+\]\]\s*', '', text, flags=re.M)
    out = []
    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para:
            continue
        if re.match(r'^#{1,6} ', para):
            lvl = len(para.split(' ')[0]); out.append('#' * min(6, lvl + 1) + ' ' + para.split(' ', 1)[1].replace('\n', ' '))
        elif re.fullmatch(r'\[(p\. [^\]]+|PDF \d+)\]', para):
            out.append(para)
        else:
            out.append(re.sub(r'\s+', ' ', para.replace('\n', ' ')))
    return out


def ocr_page(f, p, lang):
    """Tesseract on one PDF page (local): pdftoppm -> png -> text"""
    import tempfile
    d = tempfile.mkdtemp()
    subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', '300', '-gray', '-png', '-singlefile', f, f'{d}/pg'], check=True)
    r = subprocess.run(['tesseract', f'{d}/pg.png', '-', '-l', lang, '--psm', '4'], capture_output=True, text=True)
    return r.stdout


def mode_text():
    f = os.path.abspath(SRC); ext = f.rsplit('.', 1)[-1].lower()
    out, npages = [], 0
    add = out.append
    if ext == 'pdf':
        info = subprocess.run(['pdfinfo', f], capture_output=True, text=True).stdout
        n = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        m = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info)
        Wd, Ht = float(m.group(1)), float(m.group(2))
        first, last = int(opt.get('--first', 1)), int(opt.get('--last', n))
        lang = opt.get('--ocr', '')
        nocr = 0
        for p in range(first, last + 1):
            txt = pdf_half(f, p, 0, int(Wd) + 2, int(Ht) + 2)
            if len(txt.strip()) < 40 and lang:
                txt = ocr_page(f, p, lang); nocr += 1
            fol, body, notes = parse_half(txt)
            if not body and not notes:
                continue
            add(f'[p. {fol}]' if fol else f'[PDF {p}]'); add('')
            for b in body + notes:
                add(b); add('')
            npages += 1
        otext = (f'OCR by Tesseract ({lang}) on this machine, uncorrected' if nocr and nocr >= npages * 0.5 else
                 'text layer of the PDF' + (f', {nocr} pages OCR-ed locally' if nocr else '') + ' — uncorrected where it is OCR')
    elif ext == 'epub':
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        import pathlib
        from side_by_side_html import extract_epub_text
        out = md_paras(extract_epub_text(pathlib.Path(f)))
        otext = 'text of the EPUB'
    else:
        out = md_paras(open(f, errors='replace').read())
        otext = 'OCR text as supplied (Markdown/plain), uncorrected unless the file says otherwise' if ext in ('md', 'txt') else 'text as supplied'
    if not npages:
        npages = sum(len(re.findall(r'\[(?:p\. [^\]]+|PDF \d+)\]', l)) for l in out)
    head = {'title': opt.get('--title', os.path.basename(f)), 'title_en': opt.get('--title-en', ''), 'author': opt.get('--author', ''),
            'year': opt.get('--year', ''), 'original_language': opt.get('--lang', ''), 'translation_language': 'none',
            'edition_layout': 'original text only (no translation)',
            'source': f'‘{os.path.basename(f)}’ — THIS FILE IS THE SOURCE, corrections go here',
            'original_text': otext, 'translation': 'none', 'pages': npages, 'generated': f'{TODAY} by corpus.py'}
    write(opt.get('--slug') or re.sub(r'[^a-z0-9]+', '-', os.path.basename(f).lower()).strip('-')[:40], head, out)


# ---------- mode chunks: a chunk_tools translation (DIR/cNN.src.md + cNN.en.md, blocks tagged [[n]]) ----------
def mode_chunks():
    D = os.path.abspath(SRC)
    out, npages = [], 0
    add = out.append
    for src in sorted(glob.glob(f'{D}/c*.src.md')):
        en = src.replace('.src.md', '.en.md')
        if not os.path.exists(en):
            continue
        tag = lambda t: dict(re.findall(r'^\[\[(\d+)\]\]\s*(.*?)(?=^\[\[\d+\]\]|\Z)', norm_markers(t), re.M | re.S))
        A, B = tag(open(src).read()), tag(open(en).read())
        for k in sorted(A, key=int):
            a, b = re.sub(r'\s+', ' ', A[k]).strip(), re.sub(r'\s+', ' ', B.get(k, '')).strip()
            npages += len(re.findall(r'\[p\. ', a))
            if a.startswith('# ') or b.startswith('# '):
                mk = re.findall(r'\[p\. [^\]]+\]', a)
                a, b = (re.sub(r'\s*\[p\. [^\]]+\]\s*', ' ', x).strip() for x in (a, b))
                for m_ in mk:
                    add(m_); add('')
                add(f'## {a.lstrip("# ")} — {b.lstrip("# ")}'); add('')
            else:
                add(quote(a.lstrip('> '))); add(''); add(b.lstrip('> ') or '(not translated)'); add('')
    head = {'title': opt.get('--title', os.path.basename(D)), 'title_en': opt.get('--title-en', ''), 'author': opt.get('--author', ''),
            'year': opt.get('--year', ''), 'original_language': opt.get('--lang', ''), 'translation_language': 'en',
            'edition_layout': 'clean text (both columns typeset)',
            'source': f'chunk files in {os.path.basename(D)} (tag-aligned blocks) — THIS FILE IS THE SOURCE, corrections go here',
            'original_text': 'OCR of the print, corrected by the translators where evident',
            'translation': 'machine-made (Claude), reviewed against the original by Claude; no human review',
            'pages': npages, 'generated': f'{TODAY} by corpus.py'}
    write(opt.get('--slug') or os.path.basename(D), head, out)


# ---------- mode html: a Tufte-style HTML reader (ocr-tufte-html skill) or any simple HTML, one file or a folder ----------
ES = {'de', 'la', 'el', 'los', 'las', 'que', 'y', 'en', 'un', 'una', 'por', 'con', 'para', 'del', 'se', 'es', 'no', 'su'}
EN = {'the', 'of', 'and', 'to', 'in', 'a', 'that', 'is', 'it', 'for', 'with', 'as', 'was', 'on', 'by', 'this', 'are', 'be'}


def guess_lang(t):
    w = re.findall(r'\b[a-z]+\b', t.lower()[:20000])
    es, en = sum(x in ES for x in w), sum(x in EN for x in w)
    return 'es' if es >= en else 'en'


def html_to_md(src):
    body = re.search(r'<article\b[^>]*>(.*?)</article>', src, re.S) or re.search(r'<body\b[^>]*>(.*?)</body>', src, re.S)
    h = body.group(1) if body else src
    h = re.sub(r'<(script|style|nav)\b.*?</\1>', '', h, flags=re.S)
    h = re.sub(r'<(div|section|ul|ol)\b[^>]*class="[^"]*\b(toc|index-sublist|index|ornament)\b[^"]*"[^>]*>.*?</\1>', '', h, flags=re.S)
    h = re.sub(r'<(p|h\d|div)\b[^>]*class="[^"]*\b(toc-title|index-page-num|ornament)\b[^"]*"[^>]*>.*?</\1>', '', h, flags=re.S)
    h = re.sub(r'<hr\b[^>]*class="[^"]*section-break[^"]*"[^>]*>|<(p|div)\b[^>]*class="[^"]*section-break[^"]*"[^>]*>\s*(?:[^<]|<(?!/\1>))*</\1>', '<p>⁂</p>', h, flags=re.S)
    h = re.sub(r'<label\b[^>]*>.*?</label>|<input\b[^>]*>', '', h, flags=re.S)
    notes = []
    def grab_note(m):
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', m.group(1)))).strip()
        t = re.sub(r'^(\d{1,3}|\*+)\s*', '', t)                       # the sidenote repeats its own number
        notes.append(t); return f'<sup>{len(notes)}</sup>'
    h = re.sub(r'<span\b[^>]*class="[^"]*\bsidenote-number\b[^"]*"[^>]*>.*?</span>', '', h, flags=re.S)
    h = re.sub(r'<(span|div|aside)\b[^>]*class="[^"]*\b(sidenote|marginnote|footnote)\b[^"]*"[^>]*>(.*?)</\1>', lambda m: grab_note(type('M', (), {'group': lambda self, i, t=m.group(3): t})()), h, flags=re.S)
    h = re.sub(r'<span\b[^>]*class="[^"]*\bfolio\b[^"]*"[^>]*>\s*\[?([^<\]]+?)\]?\s*</span>', r' [p. \1] ', h)
    h = re.sub(r'<span\b[^>]*class="[^"]*\b(speaker|run-in)\b[^"]*"[^>]*>(.*?)</span>', r'**\2** ', h, flags=re.S)
    h = re.sub(r'<(div|p)\b[^>]*class="[^"]*\bsection-label\b[^"]*"[^>]*>(.*?)</\1>', r'<h3>\2</h3>', h, flags=re.S)
    h = re.sub(r'<(p|div)\b[^>]*class="[^"]*\bstage-direction\b[^"]*"[^>]*>(.*?)</\1>', r'<p><em>\2</em></p>', h, flags=re.S)
    h = re.sub(r'<(p|div)\b[^>]*class="[^"]*\b(subhead)\b[^"]*"[^>]*>(.*?)</\1>', r'<h3>\3</h3>', h, flags=re.S)
    h = re.sub(r'<(p|div)\b[^>]*class="[^"]*\bdraft-note\b[^"]*"[^>]*>(.*?)</\1>', r'<p><em>[Note on the text: \2]</em></p>', h, flags=re.S)
    out, inq = [], False                        # <p> is often left unclosed in hand-made HTML: split on block openers
    for part in re.split(r'(?=<(?:h[1-6]|p|blockquote|li)\b[^>]*>)', h):
        m = re.match(r'<(h[1-6]|p|blockquote|li)\b[^>]*>(.*)', part, re.S)
        if not m:
            continue
        tag, inner = m.group(1), m.group(2)
        if tag == 'blockquote':
            inq = True
        closes = '</blockquote>' in inner
        inner = re.sub(r'</(p|h[1-6]|blockquote|li|div|article|section|body|html)>', ' ', inner)
        t = inline(inner).replace('∗∗', '**')
        if t == '⁂':
            out.append('⁂')
        elif t:
            if tag[0] == 'h':
                out.append('#' * min(6, int(tag[1]) + 1) + ' ' + t)
            elif inq:
                out.append(quote(t))
            else:
                out.append(t)                       # list items (dialogue lines) as plain paragraphs
        if closes:
            inq = False
    for i, n in enumerate(notes, 1):
        out.append(f'<sup>{i}</sup> {n}')
    return out


def mode_html():
    f = os.path.abspath(SRC)
    def okey(x):
        m = re.match(r'^([\d.]+)\s', os.path.basename(x))
        return ([int(t) for t in m.group(1).strip('.').split('.') if t] if m else [999], os.path.basename(x))
    files = sorted(glob.glob(f'{f}/*.html'), key=okey) if os.path.isdir(f) else [f]
    for fp in files:
        if os.path.basename(fp) in ('reader.html', 'index.html'):
            continue
        src = open(fp, errors='replace').read()
        tm = re.search(r'<title>(.*?)</title>', src, re.S)
        title = html.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip() if tm else os.path.basename(fp)
        ym = re.match(r'^\(?(c\. ?)?(\d{4}(?:[-/]\d{2,4})?)\)?\s*(.*)$', title)
        year, title = (ym.group(2), ym.group(3)) if ym else (opt.get('--year', ''), title)
        title = re.sub(r'\s*—\s*' + re.escape(opt.get('--author', '')) + r'\s*$', '', title) if opt.get('--author') else title
        if title.lower().startswith(('complete works', 'index')):
            continue
        out = html_to_md(src)
        lang = opt.get('--lang') or guess_lang(' '.join(out))
        order = re.match(r'^([\d.]+)\s', os.path.basename(fp))
        head = {'title': title, 'title_en': '', 'author': opt.get('--author', ''), 'year': year, 'original_language': lang,
                'translation_language': 'none', 'edition_layout': 'original text only (no translation)',
                'collection': opt.get('--collection', ''), 'order': order.group(1) if order else '',
                'source': f'‘{os.path.basename(fp)}’ (HTML reader) — THIS FILE IS THE SOURCE, corrections go here',
                'original_text': 'transcription as in the HTML reader (see its note on the text)', 'translation': 'none',
                'pages': sum(l.count('[p. ') for l in out), 'generated': f'{TODAY} by corpus.py'}
        slug = opt.get('--slug') if len(files) == 1 and opt.get('--slug') else re.sub(r'[^a-z0-9]+', '-', (opt.get('--prefix', '') + ' ' + (year.split('/')[0][:4] if year else '') + ' ' + title).lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')).strip('-')[:60]
        write(slug, head, out)


{'book': mode_book, 'pdf': mode_pdf, 'index': mode_index, 'text': mode_text, 'chunks': mode_chunks, 'html': mode_html}[MODE]()
