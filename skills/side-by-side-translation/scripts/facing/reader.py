"""Static reader for the corpus: an index grouped by genre (with a genre menu and search) and one page per text
(cards: one per printed page, or per paragraph pair for clean-text editions; original left, English right; a
contents drawer; the group's notes from CORPUS/notes/<same path>.md shown on the page they concern).
Standard library only — it runs in a GitHub Action.   usage: reader.py CORPUS_DIR OUT_DIR"""
import sys, os, re, glob, html

C, O = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(O, exist_ok=True)

CSS = """
:root{--paper:#f6f3ec;--card:#fffdf8;--ink:#1f1c17;--muted:#6e675b;--toc:#a39d92;--accent:#7a2a22;--line:#e3dccd;--orig:#f0ebdf;--note:#fbf6e6;--shadow:0 1px 2px rgba(60,40,10,.06)}
@media(prefers-color-scheme:dark){:root{--paper:#161511;--card:#1e1c17;--ink:#e8e2d6;--muted:#9c9484;--toc:#6f6a60;--accent:#d49287;--line:#2c2922;--orig:#242119;--note:#26231a;--shadow:none}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;font-size:17px;line-height:1.55}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--paper) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.top .in{max-width:1240px;margin:0 auto;padding:.7rem 1.2rem;display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}
.top h1{font-size:1.1rem;font-weight:normal;margin:0;letter-spacing:.01em}.top h1 i{color:var(--ink)}
.top .sub{color:var(--muted);font-size:.85rem}.top .back{font-size:.85rem;letter-spacing:.03em;text-transform:uppercase}
.chip{display:inline-block;font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:.05rem .55rem;margin-left:.3rem;vertical-align:middle;white-space:nowrap}
.wrap{max-width:1240px;margin:0 auto;padding:1.4rem 1.2rem 5rem}
/* index */
.hero{padding:2.4rem 0 1.2rem}.hero h1{font-size:2rem;font-weight:normal;margin:0 0 .3rem;letter-spacing:-.01em}.hero p{margin:0;color:var(--muted);max-width:60ch}
.controls{display:flex;gap:.7rem;flex-wrap:wrap;align-items:center;margin:1rem 0 1.6rem;position:sticky;top:3.1rem;background:var(--paper);padding:.6rem 0;z-index:4}
select,input[type=search]{font:inherit;font-size:.95rem;padding:.45rem .7rem;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
input[type=search]{flex:1;min-width:14rem}.controls .n{color:var(--muted);font-size:.85rem;margin-left:auto}
.genre{margin:0 0 2rem}.genre h2{font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:normal;margin:0 0 .5rem;padding-bottom:.35rem;border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:1fr auto;gap:.6rem 1.4rem;padding:.6rem .2rem;border-bottom:1px solid var(--line);align-items:baseline}
.row:last-child{border-bottom:0}.row .t a{font-size:1.05rem}.row .t .en{color:var(--muted);font-size:.92rem;display:block}
.row .m{color:var(--muted);font-size:.82rem;white-space:nowrap;text-align:right}.row .m .chip{margin-left:.35rem}
.hidden{display:none!important}
/* text page */
.page{display:grid;grid-template-columns:250px minmax(0,1fr);gap:2rem}
.side{position:sticky;top:4.2rem;align-self:start;max-height:calc(100vh - 5rem);overflow:auto;font-size:.84rem;padding-right:.8rem;scrollbar-width:thin;scrollbar-color:var(--line) transparent;color:var(--toc)}
.side h3{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--toc);font-weight:normal;margin:0 0 .5rem}
.side a{display:block;color:var(--toc);padding:.16rem 0 .16rem .6rem;border-left:2px solid transparent;margin-left:-.6rem;line-height:1.35;transition:color .15s}
.side a:hover,.side a.on{color:var(--ink);border-left-color:var(--accent);text-decoration:none}.side .l3{padding-left:1.4rem}.side .l4{padding-left:2.2rem}
.side .meta{color:var(--toc);line-height:1.4;margin:0 0 1rem;font-size:.8rem}
.card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);padding:1.1rem 1.3rem 1rem;margin:0 0 1.1rem;display:grid;grid-template-columns:1fr 1fr;gap:1.4rem}
.card.mono{grid-template-columns:1fr;max-width:48rem}
.card .pg{position:absolute;top:-.62rem;left:1rem;font-size:.72rem;letter-spacing:.08em;color:var(--accent);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:.02rem .55rem}
.card h2,.card h3,.card h4,.card h5{grid-column:1/-1;font-weight:normal;text-align:center;margin:.3rem 0 .5rem;line-height:1.3}
.card h2{font-size:1.3rem;letter-spacing:.02em}.card h3{font-size:1.1rem}.card h4{font-size:1rem;font-style:italic}
.card .o{background:var(--orig);border-radius:7px;padding:.75rem .9rem;font-size:.96em}
.card .o p,.card .e p{margin:0 0 .75em;text-align:justify;text-align-last:left;hyphens:auto;-webkit-hyphens:auto;hyphenate-limit-chars:6 3 3;overflow-wrap:anywhere;line-height:1.6}
.card .o p:last-child,.card .e p:last-child{margin-bottom:0}.card .o,.card .e{min-width:0;display:flex;flex-direction:column}
.card .fn{margin-top:auto;padding-top:.5rem;border-top:1px solid var(--line);font-size:.84em;line-height:1.45;color:var(--muted)}
.card .fn p{margin:0 0 .3em;text-align:justify;text-align-last:left;hyphens:auto}.card .fn p:last-child{margin-bottom:0}.card .o .fn{border-top-color:color-mix(in srgb,var(--line) 60%,var(--orig))}
.card .fn{margin-top:.8rem}
.card.mono .e{max-width:66ch}.gnotes p,.notes p{text-align:justify;text-align-last:left;hyphens:auto}
.card p.sep{text-align:center;color:var(--muted);letter-spacing:.4em}
.pg-in{color:var(--accent);font-size:.72em;letter-spacing:.04em;vertical-align:.1em}
.card .note{font-size:.88em;color:var(--muted)}
.notes{grid-column:1/-1;background:var(--note);border-top:1px dashed var(--line);margin:.4rem -1.3rem -1rem;padding:.7rem 1.3rem .9rem;border-radius:0 0 10px 10px;font-size:.92em}
.notes h5{margin:0 0 .3rem;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:normal;text-align:left}
.notes p{margin:0 0 .5em}.notes .who{color:var(--muted);font-size:.85em}
.gnotes{background:var(--note);border:1px solid var(--line);border-radius:10px;padding:1rem 1.3rem;margin:0 0 1.2rem;font-size:.95em}.gnotes h3{margin:0 0 .4rem;font-weight:normal;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
sup{font-size:.7em;line-height:0}.toolbar{display:flex;gap:.7rem;align-items:center;margin:0 0 1.2rem}.toolbar input{max-width:24rem}
@media(max-width:900px){.page{grid-template-columns:1fr}.side{position:static;max-height:none}.card{grid-template-columns:1fr}.row{grid-template-columns:1fr}.row .m{text-align:left}}
"""
JS_INDEX = """
const sel=document.getElementById('g'),lang=document.getElementById('l'),q=document.getElementById('q'),n=document.getElementById('n');
function apply(){const g=sel.value,L=lang.value,t=q.value.toLowerCase();let k=0;
 document.querySelectorAll('.genre').forEach(s=>{let any=false;s.querySelectorAll('.row').forEach(r=>{const ok=(g==='all'||s.dataset.genre===g)&&(L==='all'||r.dataset.lang===L)&&(t.length<2||r.textContent.toLowerCase().includes(t));r.classList.toggle('hidden',!ok);if(ok){any=true;k++}});s.classList.toggle('hidden',!any)});
 n.textContent=k+' text'+(k===1?'':'s');try{localStorage.setItem('fe-genre',g)}catch(e){}}
[sel,lang].forEach(e=>e.addEventListener('change',apply));q.addEventListener('input',apply);
try{const s=localStorage.getItem('fe-genre');if(s&&[...sel.options].some(o=>o.value===s))sel.value=s}catch(e){}apply();
"""
JS_PAGE = """
const links=[...document.querySelectorAll('.side a[href^="#"]')];const map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
if(links.length&&'IntersectionObserver' in window){let cur=null;const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){const a=map.get(e.target.id);if(a){if(cur)cur.classList.remove('on');a.classList.add('on');cur=a;a.scrollIntoView({block:'nearest'})}}})},{rootMargin:'-10% 0px -80% 0px'});map.forEach((a,id)=>{const el=document.getElementById(id);if(el)io.observe(el)})}
const q=document.getElementById('q');if(q){q.addEventListener('input',()=>{const t=q.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>{c.classList.toggle('hidden',t.length>1&&!c.textContent.toLowerCase().includes(t))})})}
"""


def md_inline(t):
    t = html.escape(t, quote=False).replace('&lt;sup&gt;', '<sup>').replace('&lt;/sup&gt;', '</sup>')
    t = re.sub(r'\*\*(\S(?:[^*]*?\S)?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*(\S(?:[^*]*?\S)?)\*', r'<em>\1</em>', t)
    t = re.sub(r'\[(p\. [^\]]+|scan \d+|PDF \d+)\]', r'<span class="pg-in">[\1]</span>', t)
    return t


def header(path):
    s = open(path).read()
    m = re.match(r'---\n(.*?)\n---\n', s, re.S)
    h = dict(re.findall(r'^(\w+): (.*)$', m.group(1), re.M)) if m else {}
    return {k: v.strip('"') for k, v in h.items()}, (s[m.end():] if m else s)


def load_notes(rel):
    """CORPUS/notes/<rel>.md -> (general: [html], by_page: {label: [html]}); a '## [p. N] …' heading opens a note"""
    f = f'{C}/notes/{rel}.md'
    if not os.path.exists(f):
        return [], {}
    general, by_page = [], {}
    cur, label = [], None
    def flush():
        if not cur:
            return
        body = ''.join(f'<p>{md_inline(x)}</p>' for x in cur if x.strip())
        (by_page.setdefault(label, []) if label else general).append(body)
    for block in re.split(r'\n\s*\n', open(f).read().strip()):
        hm = re.match(r'^#{1,6}\s+(.*)$', block.strip(), re.S)
        if hm:
            flush(); cur = []
            t = hm.group(1).replace('\n', ' ')
            pm = re.search(r'\[(?:p\. |scan |PDF )([^\]]+)\]', t)
            label = 'p. ' + pm.group(1) if pm else None
            rest = re.sub(r'\[p\. [^\]]+\]\s*', '', t).strip()
            if rest:
                cur.append(f'**{rest}**')
        else:
            cur.append(block.strip().replace('\n', ' '))
    flush()
    return general, by_page


def render(path):
    rel = os.path.relpath(path, C)[:-3]
    h, body = header(path)
    g = lambda k: h.get(k, '')
    pairs = g('edition_layout').startswith('clean text')
    mono = g('translation_language') == 'none'
    NOTE = re.compile(r'^(\d{1,3}\s?[a-c]?\)|\*+\)|\(\d{1,3}\)|[†‡]|<sup>[^<]*</sup>\s)')
    paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    cards, toc = [], []
    cur = None

    def new_card(label):
        nonlocal cur
        cur = {'id': f'c{len(cards) + 1}', 'label': label, 'o': [], 'e': [], 'h': [], 'on': [], 'en': []}
        cards.append(cur)
    new_card('')
    for p in paras[2:]:
        mk = re.fullmatch(r'\[(p\. [^\]]+|scan \d+|PDF \d+)\]', p)
        if mk:
            new_card(mk.group(1)); continue
        hm = re.match(r'^(#{2,6}) (.*)$', p, re.S)
        if hm:
            lvl = len(hm.group(1)); txt = md_inline(hm.group(2).replace('\n', ' '))
            if cur['e'] or cur['o']:                      # a heading opens a new box (a section, when there are no pages)
                new_card(cur['label'])
            toc.append((lvl, re.sub('<[^>]+>', '', txt), cur['id']))
            cur['h'].append(f'<h{lvl}>{txt}</h{lvl}>'); continue
        if p == '⁂':
            cur['e'].append('<p class="sep">⁂</p>'); continue
        if p.startswith('>'):
            txt = ' '.join(l.lstrip('> ').strip() for l in p.split('\n'))
            m2 = re.search(r'\[(?:p\. |scan |PDF )([^\]]+)\]', txt)
            if m2 and (cur['o'] or cur['e']) and not NOTE.match(txt):   # one box per page: the paragraph in which a page begins opens it
                new_card(m2.group(0)[1:-1])
            elif m2 and not cur['label']:
                cur['label'] = m2.group(0)[1:-1]
            if txt:
                cur['on' if NOTE.match(txt) else 'o'].append(f'<p>{md_inline(txt)}</p>')
            continue
        im = re.search(r'\[(?:p\. |scan |PDF )([^\]]+)\]', p)
        if mono and im and (cur['e'] or cur['h']):
            new_card(im.group(0)[1:-1])
        elif im and not cur['label']:
            cur['label'] = im.group(0)[1:-1]
        cur['en' if NOTE.match(p) else 'e'].append(f'<p>{md_inline(p.replace(chr(10), " "))}</p>')
    for c in cards:
        if not c['label']:
            m2 = re.search(r'\[(?:p\. |scan |PDF )([^\]]+)\]', ' '.join(c['o'] + c['e']))
            c['label'] = m2.group(0)[1:-1] if m2 else ''
    general, by_page = load_notes(rel)
    ol = g('original_language') or 'de'
    seen = set()
    depth = '../' * rel.count('/')
    title = f'{html.escape(g("author"))}, <i>{html.escape(g("title"))}</i>' + (f' ({html.escape(g("year"))})' if g('year') else '')
    chips = ''.join(f'<span class="chip">{html.escape(x)}</span>' for x in (
        g('original_language') + ('→en' if not mono else ''), 'original only' if mono else g('edition_layout').split(' (')[0], g('genre')) if x)
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>{html.escape(g("author"))}, {html.escape(g("title"))}</title><style>{CSS}</style></head><body>'
           f'<div class="top"><div class="in"><a class="back" href="{depth}index.html">← Editions</a><h1>{title}'
           f'{(" — <i>" + html.escape(g("title_en")) + "</i>") if g("title_en") else ""}</h1>{chips}</div></div>'
           f'<div class="wrap"><div class="page"><aside class="side">'
           f'<p class="meta">{html.escape(g("original_text"))}.' + (f' Translation: {html.escape(g("translation"))}.' if not mono else '') + '</p>'
           f'<div class="toolbar"><input id="q" type="search" placeholder="find on this page"></div>']
    if toc:
        out.append('<h3>Contents</h3>' + ''.join(f'<a class="l{l}" href="#{cid}">{html.escape(t)}</a>' for l, t, cid in toc))
    out.append('</aside><main>')
    if general:
        out.append('<div class="gnotes"><h3>Notes on this text</h3>' + ''.join(general) + '</div>')
    def col(cls, body, notes, lang, empty=''):
        fn = f'<div class="fn">{"".join(notes)}</div>' if notes else ''
        return f'<div class="{cls}" lang="{lang}">{"".join(body) or empty}{fn}</div>'
    for c in cards:
        if not (c['o'] or c['e'] or c['h'] or c['on'] or c['en']):
            continue
        notes = ''
        if c['label'] in by_page and c['label'] not in seen:
            seen.add(c['label'])
            notes = f'<div class="notes"><h5>Notes · {html.escape(c["label"])}</h5>{"".join(by_page[c["label"]])}</div>'
        lab = f'<span class="pg">{html.escape(c["label"])}</span>' if c['label'] else ''
        if mono:
            out.append(f'<section class="card mono" id="{c["id"]}">{lab}{"".join(c["h"])}{col("e", c["e"], c["en"], ol)}{notes}</section>')
        else:
            out.append(f'<section class="card" id="{c["id"]}">{lab}{"".join(c["h"])}'
                       f'{col("o", c["o"], c["on"], ol, "<p class=note>original not in the corpus for this page — see the PDF edition</p>")}'
                       f'{col("e", c["e"], c["en"], "en")}{notes}</section>')
    orphan = [l for l in by_page if l not in seen]
    if orphan:
        out.append('<div class="gnotes"><h3>Notes on pages not shown separately</h3>' + ''.join(f'<p><b>{html.escape(l)}</b></p>' + ''.join(by_page[l]) for l in orphan) + '</div>')
    out.append(f'</main></div></div><script>{JS_PAGE}</script></body></html>')
    os.makedirs(os.path.dirname(f'{O}/{rel}.html'), exist_ok=True)
    open(f'{O}/{rel}.html', 'w').write('\n'.join(out))
    return rel, h, len(cards)


def order_key(x):
    m = re.search(r'^order: (.*)$', open(x).read(), re.M)
    return (os.path.dirname(x), [float(t) if re.fullmatch(r'\d+(\.\d+)?', t) else 0 for t in (m.group(1).split('.') if m else [])], x)


entries = []
for f in sorted(glob.glob(f'{C}/*.md')) + sorted(glob.glob(f'{C}/*/*.md'), key=order_key):
    if os.path.basename(f) in ('README.md', 'PROJECT-INSTRUCTIONS.md') or '/glossaries/' in f or '/notes/' in f:
        continue
    rel, h, n = render(f)
    entries.append((rel, h))
    print(rel, n, 'cards')

genres = {}
for rel, h in entries:
    genres.setdefault(h.get('genre') or 'Other', []).append((rel, h))
order = sorted(genres, key=lambda k: (k == 'Other', k))
langs = sorted({h.get('original_language', '') for _, h in entries if h.get('original_language')})
rows = []
for gname in order:
    items = sorted(genres[gname], key=lambda e: (e[1].get('collection', ''), e[1].get('author', '').split()[-1] if e[1].get('author') else '', e[1].get('year', '')))
    rr = []
    for rel, h in items:
        g = lambda k: h.get(k, '')
        mono = g('translation_language') == 'none'
        chips = f'<span class="chip">{html.escape(g("original_language"))}{"" if mono else "→en"}</span>' + (
            '<span class="chip">original only</span>' if mono else f'<span class="chip">{html.escape(g("edition_layout").split(" (")[0])}</span>')
        rr.append(f'<div class="row" data-lang="{html.escape(g("original_language"))}"><div class="t"><a href="{rel}.html">{html.escape(g("author"))}, <i>{html.escape(g("title"))}</i></a>'
                  f'{(" (" + html.escape(g("year")) + ")") if g("year") else ""}{(" · " + html.escape(g("collection"))) if g("collection") else ""}'
                  f'{("<span class=en>" + html.escape(g("title_en")) + "</span>") if g("title_en") else ""}</div>'
                  f'<div class="m">{g("pages")} pp.{chips}</div></div>')
    rows.append(f'<section class="genre" data-genre="{html.escape(gname)}"><h2>{html.escape(gname)}</h2>{"".join(rr)}</section>')
opts = ''.join(f'<option value="{html.escape(k)}">{html.escape(k)} ({len(genres[k])})</option>' for k in order)
lopts = ''.join(f'<option value="{l}">{l}</option>' for l in langs)
open(f'{O}/index.html', 'w').write(
    f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>Facing editions</title><style>{CSS}</style></head><body>'
    f'<div class="top"><div class="in"><h1>Facing editions</h1><span class="sub">bilingual editions and original texts of the research group</span></div></div>'
    f'<div class="wrap"><div class="hero"><h1>The library</h1><p>Original texts beside new English translations, page by page, and originals without a translation. '
    f'Translations are machine-made and model-reviewed, not human-revised; each page says where its text comes from.</p></div>'
    f'<div class="controls"><select id="g"><option value="all">All genres</option>{opts}</select><select id="l"><option value="all">All languages</option>{lopts}</select>'
    f'<input id="q" type="search" placeholder="search author or title"><span class="n" id="n"></span></div>'
    f'{"".join(rows)}</div><script>{JS_INDEX}</script></body></html>')
print(f'{O}/index.html: {len(entries)} texts in {len(genres)} genres')
