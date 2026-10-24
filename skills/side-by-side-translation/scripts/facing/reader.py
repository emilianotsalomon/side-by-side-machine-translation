"""Static reader for the corpus: an index grouped by genre (with a genre menu and search) and one page per text
(cards: one per printed page, or per paragraph pair for clean-text editions; original left, English right; a
contents drawer; the group's notes from CORPUS/notes/<same path>.md shown on the page they concern).
Standard library only — it runs in a GitHub Action.   usage: reader.py CORPUS_DIR OUT_DIR"""
import sys, os, re, glob, html

import json, shutil
C, O = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(O, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = json.load(open(f'{HERE}/site.json')) if os.path.exists(f'{HERE}/site.json') else {}
REPO = SITE.get('repo', '')                          # "owner/name": shared annotations are written to annotations/<text>.json there
if os.path.exists(f'{HERE}/annot.js'):
    shutil.copy(f'{HERE}/annot.js', f'{O}/annot.js')
ANN = os.path.join(os.path.dirname(C), 'annotations')
if os.path.isdir(ANN):
    shutil.copytree(ANN, f'{O}/annotations', dirs_exist_ok=True)

CSS = """
:root{--paper:#f6f3ec;--card:#fffdf8;--ink:#1f1c17;--muted:#6e675b;--toc:#a39d92;--accent:#7a2a22;--line:#e3dccd;--orig:#f0ebdf;--note:#fbf6e6;--shadow:0 1px 2px rgba(60,40,10,.06)}
@media(prefers-color-scheme:dark){:root{--paper:#161511;--card:#1e1c17;--ink:#e8e2d6;--muted:#9c9484;--toc:#6f6a60;--accent:#d49287;--line:#2c2922;--orig:#242119;--note:#26231a;--shadow:none}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;font-size:17px;line-height:1.55}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--paper) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.top .in{margin:0 auto;padding:.6rem 1.4rem;display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap}
.top h1{font-size:1.1rem;font-weight:normal;margin:0;letter-spacing:.01em}.top h1 i{color:var(--ink)}
.top .sub{color:var(--muted);font-size:.85rem}.top .back{font-size:.85rem;letter-spacing:.03em;text-transform:uppercase}
.chip{display:inline-block;font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:.05rem .55rem;margin-left:.3rem;vertical-align:middle;white-space:nowrap}
.wrap{margin:0 auto;padding:1.2rem 1.4rem 5rem}.wrap.index{max-width:1100px}
/* index */
.hero{padding:2.4rem 0 1.2rem}.hero h1{font-size:2rem;font-weight:normal;margin:0 0 .3rem;letter-spacing:-.01em}.hero p{margin:0;color:var(--muted);max-width:60ch}
.controls{display:flex;gap:.9rem;flex-wrap:wrap;align-items:center;margin:1rem 0 1.6rem;position:sticky;top:3.1rem;background:var(--paper);padding:.6rem 0;z-index:4}
.seg{display:inline-flex;align-items:center;gap:0;border:1px solid var(--line);border-radius:999px;background:var(--card);padding:.15rem;font-size:.82rem}
.seg .lbl{color:var(--muted);padding:0 .7rem 0 .8rem;letter-spacing:.04em;text-transform:uppercase;font-size:.7rem}
.seg button{font:inherit;font-size:.85rem;border:0;background:transparent;color:var(--muted);padding:.3rem .8rem;border-radius:999px;cursor:pointer}.seg button.on{background:var(--orig);color:var(--ink)}.seg button:hover{color:var(--ink)}
select,input[type=search]{font:inherit;font-size:.95rem;padding:.45rem .7rem;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
input[type=search]{flex:1;min-width:14rem}.controls .n{color:var(--muted);font-size:.85rem;margin-left:auto}
.genre{margin:0;border-bottom:1px solid var(--line)}.genre summary{display:flex;align-items:baseline;gap:1rem;padding:.9rem .2rem;cursor:pointer;list-style:none}
.genre summary::-webkit-details-marker{display:none}.genre summary::before{content:"›";color:var(--muted);display:inline-block;transition:transform .15s;width:.8rem}.genre[open] summary::before{transform:rotate(90deg)}
.genre h2{font-size:1.05rem;font-weight:normal;margin:0;letter-spacing:.01em}.genre .cnt{color:var(--muted);font-size:.82rem;margin-left:auto}
.genre[open]{padding-bottom:.6rem}.genre .row{margin-left:1.8rem}
.row{display:grid;grid-template-columns:1fr auto;gap:.6rem 1.4rem;padding:.6rem .2rem;border-bottom:1px solid var(--line);align-items:baseline}
.row:last-child{border-bottom:0}.row .t a{font-size:1.05rem}.row .t .en{color:var(--muted);font-size:.92rem;display:block}
.row .m{color:var(--muted);font-size:.82rem;white-space:nowrap;text-align:right}.row .m .chip{margin-left:.35rem}
.hidden{display:none!important}
/* text page */
.page{display:grid;grid-template-columns:var(--side-w,250px) 10px minmax(0,1fr);gap:0 1rem;--side-w:250px;--cm-w:300px}
.hdl{cursor:col-resize;border-radius:4px;background:transparent;position:relative}.hdl::after{content:"";position:absolute;top:0;bottom:0;left:4px;width:2px;background:var(--line);border-radius:2px}.hdl:hover::after,.hdl.on::after{background:var(--accent)}
.hdl.r{display:none}body.an-with-comments .hdl.r{display:block}body.resizing{user-select:none;cursor:col-resize}
.tog{position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:6;display:flex;flex-direction:column;align-items:center;gap:.15rem;width:1.7rem;padding:.6rem 0 .5rem;border:1px solid var(--line);border-left:0;border-radius:0 8px 8px 0;background:var(--card);color:var(--muted);cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.08);font:inherit}
.tog span{font-size:1.3rem;line-height:1}.tog small{writing-mode:vertical-rl;font-size:.6rem;letter-spacing:.14em;text-transform:uppercase}.tog:hover{color:var(--ink);background:var(--orig)}
body.noside .tog span{transform:scaleX(-1)}body.noside .tog{left:0}
body.noside .page{grid-template-columns:0 0 minmax(0,1fr)}body.noside.an-with-comments .page{grid-template-columns:0 0 minmax(0,1fr) 10px var(--cm-w,300px)}
body.noside .side,body.noside .hdl.l{visibility:hidden;overflow:hidden;padding:0;min-width:0;width:0}
body.noside .page{gap:0 0}body.noside main{padding-left:.2rem}
.side{position:sticky;top:4.2rem;align-self:start;max-height:calc(100vh - 5rem);overflow:auto;font-size:.84rem;padding-right:.8rem;scrollbar-width:thin;scrollbar-color:var(--line) transparent;color:var(--toc)}
.side h3{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--toc);font-weight:normal;margin:0 0 .5rem}
.side a{display:block;color:var(--toc);padding:.16rem 0 .16rem .6rem;border-left:2px solid transparent;margin-left:-.6rem;line-height:1.35;transition:color .15s}
.side a:hover,.side a.on{color:var(--ink);border-left-color:var(--accent);text-decoration:none}.side .l3{padding-left:1.4rem}.side .l4{padding-left:2.2rem}
.side .meta{color:var(--toc);line-height:1.4;margin:0 0 1rem;font-size:.8rem}
.card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);padding:1.1rem 1.3rem 1rem;margin:0 0 1.1rem;display:grid;grid-template-columns:1fr 1fr;gap:1.4rem}
.card.mono{grid-template-columns:1fr;max-width:48rem}
.card.pairs{display:block;padding:1.1rem 1.3rem 1rem 0;background:linear-gradient(to right,var(--orig) 0,var(--orig) calc(50% - .35rem),var(--card) calc(50% - .35rem))}
.card.pairs h2,.card.pairs h3,.card.pairs h4{display:block;margin-left:1.3rem}
.row{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem;margin:0 0 .75em}.row.single{grid-template-columns:1fr}.row.single .e{max-width:66ch;margin-left:1.3rem}.row:last-child{margin-bottom:0}
.row .o{padding:0 .9rem 0 1.3rem;font-size:.96em}.row .o p{margin:0}.row .e p{margin:0}
.card.pairs .pg{left:1rem}
.fnrows{margin-top:.9rem;padding-top:.6rem;border-top:1px solid var(--line)}.fnrow .o,.fnrow .e{font-size:.84em;line-height:1.45;color:var(--muted)}
.fnrow{margin-bottom:.3rem}
.card .pg{position:absolute;top:-.62rem;left:1rem;font-size:.72rem;letter-spacing:.08em;color:var(--accent);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:.02rem .55rem}
.card h2,.card h3,.card h4,.card h5{grid-column:1/-1;font-weight:normal;text-align:center;margin:.3rem 0 .5rem;line-height:1.3}
.card h2{font-size:1.3rem;letter-spacing:.02em}.card h3{font-size:1.1rem}.card h4{font-size:1rem;font-style:italic}
.card .o{background:var(--orig);border-radius:7px;padding:.75rem .9rem;font-size:.96em}
.card .o p,.card .e p{margin:0 0 .75em;text-align:justify;text-align-last:left;hyphens:auto;-webkit-hyphens:auto;hyphenate-limit-chars:6 3 3;overflow-wrap:anywhere;line-height:1.6}
.card .o p:last-child,.card .e p:last-child{margin-bottom:0}.card .o,.card .e{min-width:0}
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
/* annotations */
mark.an{background:transparent;color:inherit;border-radius:2px}mark.an.hl.straw{background:rgba(214,188,96,.28)}mark.an.hl.sage{background:rgba(120,160,120,.26)}mark.an.hl.rose{background:rgba(200,120,120,.24)}
mark.an.ul{text-decoration:underline;text-decoration-color:rgba(122,42,34,.55);text-decoration-thickness:1.5px;text-underline-offset:3px}
mark.an.st{text-decoration:line-through;text-decoration-color:rgba(60,60,60,.55);text-decoration-thickness:1.5px}
mark.an.cm{background:rgba(214,188,96,.18);box-shadow:0 1.5px 0 rgba(122,42,34,.45)}mark.an.on{background:rgba(214,188,96,.45)}
@media(prefers-color-scheme:dark){mark.an.hl.straw{background:rgba(214,188,96,.22)}mark.an.hl.sage{background:rgba(120,160,120,.22)}mark.an.hl.rose{background:rgba(200,120,120,.2)}}
.an-ctl{margin-left:auto;display:flex;gap:.9rem;align-items:center;font-size:.8rem;color:var(--muted)}.an-ctl label{display:flex;gap:.3rem;align-items:center;cursor:pointer}
.an-btn{font:inherit;font-size:.78rem;padding:.2rem .6rem;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--muted);cursor:pointer}.an-btn:hover{color:var(--ink)}
.an-bar{position:absolute;z-index:20;display:flex;gap:2px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:3px;box-shadow:0 4px 14px rgba(0,0,0,.12)}
.an-bar button{font:inherit;font-size:.9rem;width:2rem;height:1.9rem;border:0;background:transparent;border-radius:5px;cursor:pointer;color:var(--ink)}.an-bar button:hover{background:var(--orig)}
.an-bar .sw{display:inline-block;width:14px;height:14px;border-radius:3px}.an-bar .sw.straw{background:rgba(214,188,96,.6)}.an-bar .sw.sage{background:rgba(120,160,120,.6)}.an-bar .sw.rose{background:rgba(200,120,120,.6)}
.an-gutter{position:relative;display:none}body.an-with-comments .page{grid-template-columns:var(--side-w,250px) 10px minmax(0,1fr) 10px var(--cm-w,300px)}body.an-with-comments .an-gutter{display:block}
.an-cm{position:absolute;left:0;right:0;background:var(--note);border:1px solid var(--line);border-radius:8px;padding:.55rem .75rem;font-size:.84rem;line-height:1.4;box-shadow:var(--shadow);cursor:pointer}
.an-cm .an-meta{color:var(--muted);font-size:.74rem;display:flex;gap:.3rem;align-items:baseline}.an-cm .an-meta b{color:var(--ink)}.an-x{margin-left:auto;border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:1rem}
.an-cm .an-q{color:var(--muted);font-style:italic;margin:.2rem 0;font-size:.78rem}.an-cm .an-t{color:var(--ink)}
.an-dlg{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:30;display:flex;align-items:center;justify-content:center}.an-dlg.hidden{display:none}
.an-box{background:var(--card);color:var(--ink);max-width:34rem;padding:1.4rem 1.6rem;border-radius:10px;font-size:.92rem;line-height:1.45}.an-box h3{margin:0 0 .6rem;font-weight:normal}
.an-box label{display:block;margin:.6rem 0;font-size:.85rem;color:var(--muted)}.an-box input{display:block;width:100%;font:inherit;padding:.4rem .6rem;border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink);margin-top:.2rem}
.an-row{display:flex;gap:.6rem;margin-top:.8rem}
@media(max-width:900px){.page{grid-template-columns:1fr}body.an-with-comments .page{grid-template-columns:1fr}.hdl{display:none!important}.an-gutter{position:static}.an-cm{position:static;width:auto;margin:.4rem 0}.side{position:static;max-height:none}.card,.row{grid-template-columns:1fr}.row{grid-template-columns:1fr}.row .m{text-align:left}}
"""
JS_INDEX = """
const q=document.getElementById('q'),n=document.getElementById('n'),list=document.getElementById('list'),pool=document.getElementById('pool'),seg=document.getElementById('by');
const rows=[...pool.querySelectorAll('.row')];const st=k=>{try{return localStorage.getItem(k)}catch(e){return null}};const sv=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
let by=st('fe-by')||'author';const open=new Set((st('fe-open-'+by)||'').split('|').filter(Boolean));
const keyOf=r=>({author:r.dataset.author,genre:r.dataset.genre,lang:r.dataset.lang,century:r.dataset.century})[by];
const sortOf=r=>by==='author'?[parseFloat(r.dataset.order||'0')||0,+r.dataset.year||9e9,r.textContent]:[r.dataset.sort,+r.dataset.year||9e9];
function build(){list.innerHTML='';const groups=new Map();rows.forEach(r=>{const k=keyOf(r);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)});
 const keys=[...groups.keys()].sort((a,b)=>{if(by==='author'){const sa=groups.get(a)[0].dataset.sort,sb=groups.get(b)[0].dataset.sort;return sa.localeCompare(sb)}if(a==='Other'||a==='undated')return 1;if(b==='Other'||b==='undated')return -1;return a.localeCompare(b)});
 keys.forEach(k=>{const d=document.createElement('details');d.className='genre';d.dataset.key=k;if(open.has(k))d.open=true;
  const items=groups.get(k).sort((x,y)=>{const a=sortOf(x),b=sortOf(y);for(let i=0;i<a.length;i++){if(a[i]<b[i])return -1;if(a[i]>b[i])return 1}return 0});
  d.innerHTML='<summary><h2></h2><span class="cnt">'+items.length+' text'+(items.length===1?'':'s')+'</span></summary>';d.querySelector('h2').textContent=k;items.forEach(r=>d.appendChild(r));
  d.addEventListener('toggle',()=>{if(d.open)open.add(k);else open.delete(k);sv('fe-open-'+by,[...open].join('|'))});list.appendChild(d)});apply();}
function apply(){const t=q.value.toLowerCase();let k=0;const searching=t.length>1;
 list.querySelectorAll('.genre').forEach(s=>{let any=false;s.querySelectorAll('.row').forEach(r=>{const ok=!searching||r.textContent.toLowerCase().includes(t);r.classList.toggle('hidden',!ok);if(ok){any=true;k++}});
  s.classList.toggle('hidden',!any);if(searching)s.open=any;else s.open=open.has(s.dataset.key)});n.textContent=searching?k+' text'+(k===1?'':'s'):'';}
seg.querySelectorAll('button').forEach(b=>{b.classList.toggle('on',b.dataset.by===by);b.onclick=()=>{by=b.dataset.by;sv('fe-by',by);open.clear();(st('fe-open-'+by)||'').split('|').filter(Boolean).forEach(x=>open.add(x));seg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));build()}});
q.addEventListener('input',apply);build();
"""
JS_PAGE = """
(function(){const pg=document.querySelector('.page');if(!pg)return;const st=k=>{try{return localStorage.getItem(k)}catch(e){return null}};const sv=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
 const tog=document.getElementById('tog');const setSide=on=>{document.body.classList.toggle('noside',!on);sv('fe-side',on?'on':'off');if(tog)tog.title=(on?'hide':'show')+' the contents (press c)';window.dispatchEvent(new Event('resize'))};
 setSide(st('fe-side')!=='off');if(tog)tog.onclick=()=>setSide(document.body.classList.contains('noside'));
 document.addEventListener('keydown',e=>{if(e.key==='c'&&!e.metaKey&&!e.ctrlKey&&!e.altKey&&!/input|textarea/i.test(e.target.tagName))setSide(document.body.classList.contains('noside'))});
 const w0=st('fe-side-w'),w1=st('fe-cm-w');if(w0)pg.style.setProperty('--side-w',w0+'px');if(w1)pg.style.setProperty('--cm-w',w1+'px');
 document.querySelectorAll('.hdl').forEach(h=>{h.addEventListener('mousedown',e=>{e.preventDefault();const side=h.dataset.for==='side';const x0=e.clientX;const cur=parseFloat(getComputedStyle(pg).getPropertyValue(side?'--side-w':'--cm-w'))||(side?250:300);
  h.classList.add('on');document.body.classList.add('resizing');
  const mv=ev=>{const d=ev.clientX-x0;const w=Math.max(120,Math.min(700,side?cur+d:cur-d));pg.style.setProperty(side?'--side-w':'--cm-w',w+'px')};
  const up=()=>{document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);h.classList.remove('on');document.body.classList.remove('resizing');sv(side?'fe-side-w':'fe-cm-w',parseFloat(getComputedStyle(pg).getPropertyValue(side?'--side-w':'--cm-w')));window.dispatchEvent(new Event('resize'))};
  document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up)})})})();
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
    paged = bool(re.search(r'\[(p\. [^\]]+|scan \d+|PDF \d+)\]', body))      # texts without any page marks: boxes per section
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
            if not paged and (cur['e'] or cur['o']):     # no page marks at all: a heading opens a new box (one per section)
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
           f'<div class="top"><div class="in"><a class="back" href="{depth}index.html">← Library</a><h1>{title}'
           f'{(" — <i>" + html.escape(g("title_en")) + "</i>") if g("title_en") else ""}</h1>{chips}</div></div>'
           f'<div class="wrap"><div class="page"><aside class="side">'
           f'<p class="meta">{html.escape(g("original_text"))}.' + (f' Translation: {html.escape(g("translation"))}.' if not mono else '') + '</p>'
           f'<div class="toolbar"><input id="q" type="search" placeholder="find on this page"></div>']
    if toc:
        out.append('<h3>Contents</h3>' + ''.join(f'<a class="l{l}" href="#{cid}">{html.escape(t)}</a>' for l, t, cid in toc))
    out.append('</aside><div class="hdl l" data-for="side"></div><main>')
    out.append('<button class="tog" id="tog" title="hide the contents (press c)" aria-label="hide or show the contents"><span>‹</span><small>contents</small></button>')
    if general:
        out.append('<div class="gnotes"><h3>Notes on this text</h3>' + ''.join(general) + '</div>')
    def rows(o, e, ol, kind=''):
        """paired rows when the two sides have the same number of paragraphs; otherwise one row with both columns"""
        if o and e and len(o) == len(e):
            return ''.join(f'<div class="row{kind}"><div class="o" lang="{ol}">{a}</div><div class="e" lang="en">{b}</div></div>' for a, b in zip(o, e))
        if not o:                                   # nothing on the original side: show what there is, full width
            return f'<div class="row single{kind}"><div class="e" lang="en">{"".join(e)}</div></div>'
        return f'<div class="row{kind}"><div class="o" lang="{ol}">{"".join(o)}</div><div class="e" lang="en">{"".join(e)}</div></div>'
    for c in cards:
        if not (c['o'] or c['e'] or c['h'] or c['on'] or c['en']):
            continue
        notes = ''
        if c['label'] in by_page and c['label'] not in seen:
            seen.add(c['label'])
            notes = f'<div class="notes"><h5>Notes · {html.escape(c["label"])}</h5>{"".join(by_page[c["label"]])}</div>'
        lab = f'<span class="pg">{html.escape(c["label"])}</span>' if c['label'] else ''
        if mono:
            fn = f'<div class="fn">{"".join(c["en"])}</div>' if c['en'] else ''
            out.append(f'<section class="card mono" id="{c["id"]}">{lab}{"".join(c["h"])}<div class="e" lang="{ol}">{"".join(c["e"])}{fn}</div>{notes}</section>')
        else:
            body = rows(c['o'], c['e'], ol)
            if not c['o'] and not c['on']:
                fn = f'<div class="fn">{"".join(c["en"])}</div>' if c['en'] else ''
                out.append(f'<section class="card mono" id="{c["id"]}">{lab}{"".join(c["h"])}<div class="e" lang="en">{"".join(c["e"])}{fn}</div>{notes}</section>')
                continue
            foot = (f'<div class="fnrows">{rows(c["on"], c["en"], ol, " fnrow")}</div>' if (c['on'] or c['en']) else '')
            out.append(f'<section class="card pairs" id="{c["id"]}">{lab}{"".join(c["h"])}{body}{foot}{notes}</section>')
    orphan = [l for l in by_page if l not in seen]
    if orphan:
        out.append('<div class="gnotes"><h3>Notes on pages not shown separately</h3>' + ''.join(f'<p><b>{html.escape(l)}</b></p>' + ''.join(by_page[l]) for l in orphan) + '</div>')
    out.append(f'</main><div class="hdl r" data-for="cm"></div><aside class="an-gutter"></aside></div></div><script>{JS_PAGE}</script>'
               + (f'<script>window.ANNOT={json.dumps({"repo": REPO, "branch": SITE.get("branch", "main"), "rel": rel, "base": depth})}</script><script src="{depth}annot.js"></script>' if REPO else '')
               + '</body></html>')
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

LANGN = {'de': 'German', 'es': 'Spanish', 'fr': 'French', 'it': 'Italian', 'la': 'Latin', 'hu': 'Hungarian', 'en': 'English', 'el': 'Greek', 'pt': 'Portuguese'}
rows = []
for rel, h in entries:
    g = lambda k: h.get(k, '')
    mono = g('translation_language') == 'none'
    chips = f'<span class="chip">{html.escape(g("original_language"))}{"" if mono else "→en"}</span>' + (
        '<span class="chip">original only</span>' if mono else f'<span class="chip">{html.escape(g("edition_layout").split(" (")[0])}</span>')
    ym = re.search(r'\d{4}', g('year')); yr = int(ym.group(0)) if ym else 0
    cent = f'{(yr - 1) // 100 + 1}th century' if yr else 'undated'
    surname = (g('author').split()[-1] if g('author') else '~')
    sortkey = f'{surname} {g("author")}'
    order_ = h.get('order', '')
    rows.append(f'<div class="row" data-author="{html.escape(g("author") or "—")}" data-sort="{html.escape(sortkey)}" data-genre="{html.escape(g("genre") or "Other")}" '
                f'data-lang="{html.escape(LANGN.get(g("original_language"), g("original_language")) or "—")}" data-century="{cent}" data-year="{yr}" data-order="{html.escape(order_)}">'
                f'<div class="t"><a href="{rel}.html">{html.escape(g("author"))}, <i>{html.escape(g("title"))}</i></a>'
                f'{(" (" + html.escape(g("year")) + ")") if g("year") else ""}{(" · " + html.escape(g("collection"))) if g("collection") else ""}'
                f'{("<span class=en>" + html.escape(g("title_en")) + "</span>") if g("title_en") else ""}</div>'
                f'<div class="m">{g("pages")} pp.{chips}</div></div>')
open(f'{O}/index.html', 'w').write(
    f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>Idealisms Working Group Shared Repository</title><style>{CSS}</style></head><body>'
    f'<div class="top"><div class="in"><h1>Idealisms Working Group Shared Repository</h1><span class="sub">bilingual editions, original texts and notes</span></div></div>'
    f'<div class="wrap index"><div class="hero"><h1>The library</h1><p>Original texts beside new English translations, page by page, and originals without a translation. '
    f'Translations are machine-made and model-reviewed, not human-revised; each page says where its text comes from.</p></div>'
    f'<div class="controls"><div class="seg" id="by"><span class="lbl">Group by</span><button data-by="author" class="on">Author</button><button data-by="genre">Genre</button>'
    f'<button data-by="lang">Language</button><button data-by="century">Century</button></div>'
    f'<input id="q" type="search" placeholder="search author or title"><span class="n" id="n"></span></div>'
    f'<div id="list"></div><div id="pool" class="hidden">{"".join(rows)}</div></div><script>{JS_INDEX}</script></body></html>')
print(f'{O}/index.html: {len(entries)} texts')
