"""Static reader for the corpus: one HTML page per edition (cards, one per printed page: original left, English
right), plus an index page.  No server, no JavaScript framework — host the output folder with GitHub Pages.
usage: reader.py CORPUS_DIR OUT_DIR        (writes OUT_DIR/index.html and OUT_DIR/<slug>.html)"""
import sys, os, re, glob, html, json

C, O = sys.argv[1], sys.argv[2]
os.makedirs(O, exist_ok=True)
CSS = """
:root{--bg:#faf8f3;--card:#fff;--ink:#1a1a1a;--mute:#6b6b6b;--rule:#ddd;--acc:#8b1a1a;--orig:#f4f1ea}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--card:#1f1f1f;--ink:#e8e4dc;--mute:#9a9a9a;--rule:#333;--acc:#e07a7a;--orig:#232120}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Georgia,'Iowan Old Style','Palatino Linotype',serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--rule);padding:.6rem 1.2rem;display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap;z-index:2}
header h1{font-size:1.05rem;margin:0;font-weight:normal}header a{color:var(--acc);text-decoration:none}header .meta{color:var(--mute);font-size:.85rem}
header input{margin-left:auto;font:inherit;font-size:.9rem;padding:.2rem .5rem;border:1px solid var(--rule);border-radius:4px;background:var(--card);color:var(--ink);width:14rem}
main{max-width:1400px;margin:0 auto;padding:1rem 1.2rem 4rem}
.card{display:grid;grid-template-columns:1fr 1fr;}.card.mono{grid-template-columns:1fr;max-width:46rem;margin-left:auto;margin-right:auto}
.card{gap:1.2rem;background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:1rem 1.2rem;margin:0 0 1rem;position:relative}
.card .pg{position:absolute;top:-.7rem;left:1rem;background:var(--bg);color:var(--acc);font-size:.8rem;padding:0 .4rem;letter-spacing:.04em}
.card .o{background:var(--orig);padding:.6rem .8rem;border-radius:4px;color:var(--ink);font-size:.95rem}
.card .e p,.card .o p{margin:0 0 .7em}.card h2,.card h3,.card h4{grid-column:1/-1;margin:.2rem 0 .4rem;font-weight:normal;text-align:center}
.card h2{font-size:1.25rem;letter-spacing:.04em}.card h3{font-size:1.05rem}.card .note{font-size:.85rem;color:var(--mute)}
sup{font-size:.7em}.hidden{display:none}@media(max-width:800px){.card{grid-template-columns:1fr}}
nav.toc{font-size:.9rem;columns:2;margin:1rem 0 2rem}nav.toc a{display:block;color:var(--ink);text-decoration:none;padding:.1rem 0}nav.toc a:hover{color:var(--acc)}
table{border-collapse:collapse;font-size:.95rem}td,th{padding:.4rem .8rem;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}th{font-weight:normal;color:var(--mute)}
"""
JS = """
const q=document.getElementById('q');if(q){q.addEventListener('input',()=>{const t=q.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>{c.classList.toggle('hidden',t.length>1&&!c.textContent.toLowerCase().includes(t))})})}
"""


def md_inline(t):
    t = html.escape(t, quote=False).replace('&lt;sup&gt;', '<sup>').replace('&lt;/sup&gt;', '</sup>')
    t = re.sub(r'\*(\S(?:[^*]*?\S)?)\*', r'<em>\1</em>', t)
    t = re.sub(r'\[(p\. [^\]]+|scan \d+|PDF \d+)\]', r'<span class="pg-in" style="color:var(--acc);font-size:.8em">[\1]</span>', t)
    return t


def render(path):
    s = open(path).read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    head = dict(re.findall(r'^(\w+): (.*)$', m.group(1), re.M)) if m else {}
    g = lambda k: head.get(k, '').strip('"')
    body = s[m.end():] if m else s
    paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    cards, cur, toc = [], None, []
    pid = 0
    pairs = g('edition_layout').startswith('clean text')
    mono = g('translation_language') == 'none'       # paragraph pairs: one card per pair, label from the inline marker
    NOTE = re.compile(r'^(\d{1,3}\s?[a-c]?\)|\*+\)|\(\d{1,3}\)|[†‡])')

    def new_card(label):
        nonlocal cur, pid
        pid += 1
        cur = {'id': f'p{pid}', 'label': label, 'o': [], 'e': [], 'h': []}
        cards.append(cur)
    new_card('')
    for p in paras[2:]:                       # skip the H1 title and the conventions paragraph
        mk = re.fullmatch(r'\[(p\. [^\]]+|scan \d+|PDF \d+)\]', p)
        if mk:
            new_card(mk.group(1)); continue
        hm = re.match(r'^(#{2,6}) (.*)$', p, re.S)
        if hm:
            lvl = len(hm.group(1)); txt = md_inline(hm.group(2).replace('\n', ' '))
            toc.append((lvl, re.sub('<[^>]+>', '', txt), cur['id']))
            cur['h'].append(f'<h{lvl} id="h{len(toc)}">{txt}</h{lvl}>'); continue
        if p.startswith('>'):
            txt = ' '.join(l.lstrip('> ').strip() for l in p.split('\n'))
            if pairs and cur['o'] and not NOTE.match(txt):
                m2 = re.search(r'\[p\. ([^\]]+)\]', txt)
                new_card('p. ' + m2.group(1) if m2 else cards[-1]['label'] if cards else '')
                cur['label'] = cur['label'] or ''
            if txt:
                cur['o'].append(f'<p>{md_inline(txt)}</p>')
            continue
        im = re.search(r'\[p\. ([^\]]+)\]', p)
        if mono and im and (cur['e'] or cur['h']):      # original-only files: a new card at every page start
            new_card('p. ' + im.group(1))
        elif mono and im and not cur['label']:
            cur['label'] = 'p. ' + im.group(1)
        cur['e'].append(f'<p>{md_inline(p.replace(chr(10), " "))}</p>')
    # inline markers inside paragraph-paired books: split cards at them is unnecessary; label from first marker
    for c in cards:
        if not c['label']:
            m2 = re.search(r'\[p\. ([^\]]+)\]', ' '.join(c['o'] + c['e']))
            c['label'] = 'p. ' + m2.group(1) if m2 else ''
    slugrel = os.path.relpath(path, C)
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>{html.escape(g("author"))}, {html.escape(g("title"))}</title><style>{CSS}</style></head><body>'
           f'<header><a href="{"../" if "/" in slugrel else ""}index.html">← Editions</a><h1>{html.escape(g("author"))}, <i>{html.escape(g("title"))}</i>'
           f'{(" (" + html.escape(g("year")) + ")") if g("year") else ""}{(" — <i>" + html.escape(g("title_en")) + "</i>") if g("title_en") else ""}</h1>'
           f'<span class="meta">{html.escape(g("original_text"))}{(" · " + html.escape(g("translation"))) if g("translation") not in ("", "none") else " · original text only"}</span>'
           f'<input id="q" type="search" placeholder="find on this page (both languages)"></header><main>']
    if toc:
        out.append('<nav class="toc">' + ''.join(f'<a href="#{cid}" style="padding-left:{(l - 2) * 1.2}rem">{html.escape(t)}</a>' for l, t, cid in toc) + '</nav>')
    for c in cards:
        if not (c['o'] or c['e'] or c['h']):
            continue
        if mono:
            out.append(f'<section class="card mono" id="{c["id"]}"><span class="pg">{html.escape(c["label"])}</span>{"".join(c["h"])}'
                       f'<div class="e">{"".join(c["e"])}</div></section>')
            continue
        out.append(f'<section class="card" id="{c["id"]}"><span class="pg">{html.escape(c["label"])}</span>{"".join(c["h"])}'
                   f'<div class="o">{"".join(c["o"]) or "<p class=note>original not in the corpus for this page — see the PDF edition</p>"}</div>'
                   f'<div class="e">{"".join(c["e"])}</div></section>')
    out.append(f'</main><script>{JS}</script></body></html>')
    slug = os.path.relpath(path, C)[:-3]
    os.makedirs(os.path.dirname(f'{O}/{slug}.html'), exist_ok=True)
    open(f'{O}/{slug}.html', 'w').write('\n'.join(out))
    return slug, head, len(cards)


rows = []
def order_key(x):
    m = re.search(r'^order: (.*)$', open(x).read(), re.M)
    return (os.path.dirname(x), [float(t) if re.fullmatch(r'\d+(\.\d+)?', t) else 0 for t in (m.group(1).split('.') if m else [])], x)


for f in sorted(glob.glob(f'{C}/*.md')) + sorted(glob.glob(f'{C}/*/*.md'), key=order_key):
    if os.path.basename(f) in ('README.md', 'PROJECT-INSTRUCTIONS.md') or '/glossaries/' in f or '/notes/' in f:
        continue
    slug, h, n = render(f)
    g = lambda k: h.get(k, '').strip('"')
    rows.append(f'<tr><td>{html.escape(g("author"))}</td><td><a href="{slug}.html"><i>{html.escape(g("title"))}</i></a>'
                f'{(" (" + html.escape(g("year")) + ")") if g("year") else ""}{(" · " + html.escape(g("collection"))) if g("collection") else ""}<br><span style="color:var(--mute)">{html.escape(g("title_en"))}</span></td>'
                f'<td>{html.escape(g("original_language"))}{"→en" if g("translation_language") != "none" else " (original only)"}</td><td>{html.escape(g("pages"))}</td><td>{html.escape(g("original_text").split(" (")[0])}</td></tr>')
    print(slug, n, 'cards')
open(f'{O}/index.html', 'w').write(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                                   f'<title>Facing editions</title><style>{CSS}</style></head><body><header><h1>Facing editions — bilingual reader</h1>'
                                   f'<span class="meta">original beside a new English translation, page by page; translations machine-made and model-reviewed, not human-revised</span></header>'
                                   f'<main><table><tr><th>author</th><th>work</th><th>languages</th><th>pages</th><th>original text</th></tr>{"".join(rows)}</table></main></body></html>')
print(f'{O}/index.html: {len(rows)} editions')
