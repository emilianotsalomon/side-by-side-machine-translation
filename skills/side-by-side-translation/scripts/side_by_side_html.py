#!/usr/bin/env python3
"""side_by_side_html.py — parallel-text HTML builder (v4).

Changes from v3:
- Fixed Roman-numeral regex: greedy longest-first (XII|XI|X|IX|VIII|…|I)
- Added --verify: anchor-based alignment check (chapter headings, footnotes)
- Removed lazy rendering: all rows rendered at page load (<1MB is instant)
- Scroll-spy: rAF-throttled scroll listener replaces IntersectionObserver
- New default design: Cormorant Garamond + IBM Plex Sans, warm parchment palette
- Single set of controls (no duplicate A−/A+)
- Appendix / Anhang detection for TOC
"""
from __future__ import annotations
import argparse, html as html_module, json, re, sys, zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_prep import MD_SUFFIXES   # .md inputs are normalised on load (headings, notes, page blocks, LLM chatter)

# ── Roman numeral pattern (greedy, longest-first) ────────────────────────────
_ROMAN_PAT = r'(?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)'
_ROMAN_RE  = re.compile(r'^(' + _ROMAN_PAT + r')\.\s')
_MARK_LEAD_RE = re.compile(r'^\s*(?:\[[^\]]{1,8}\]\s*)+')   # leading page markers such as [12] or [p. 12]

class _XHTMLTextExtractor(HTMLParser):
    BLOCK = {'p','div','h1','h2','h3','h4','h5','h6','blockquote','li','section','article','td','th'}
    SKIP = {'script','style','head','nav'}
    def __init__(self):
        super().__init__(); self._cur=[]; self._skip=0; self.blocks=[]
    def handle_starttag(self, tag, attrs):
        t=tag.lower()
        if t in self.SKIP: self._skip+=1
        elif t in self.BLOCK and not self._skip: self._flush()
    def handle_endtag(self, tag):
        t=tag.lower()
        if t in self.SKIP: self._skip=max(0,self._skip-1)
        elif t in self.BLOCK and not self._skip: self._flush()
    def handle_data(self, data):
        if not self._skip: self._cur.append(data)
    def _flush(self):
        t=' '.join(''.join(self._cur).split()).strip().replace('\xa0',' ')
        if t: self.blocks.append(t)
        self._cur=[]
    def get_blocks(self):
        self._flush(); return self.blocks

def extract_epub_text(epub_path: Path) -> str:
    with zipfile.ZipFile(epub_path,'r') as zf:
        cxml=zf.read('META-INF/container.xml').decode('utf-8',errors='replace')
        opf_path=None
        for e in ET.fromstring(cxml).iter():
            if e.tag.endswith('}rootfile') or e.tag=='rootfile':
                opf_path=e.attrib.get('full-path'); break
        if not opf_path: raise ValueError(f"No OPF rootfile: {epub_path}")
        od=str(Path(opf_path).parent); od='' if od=='.' else od
        opf_root=ET.fromstring(zf.read(opf_path).decode('utf-8',errors='replace'))
        mf={}
        for e in opf_root.iter():
            if e.tag.endswith('}item') or e.tag=='item':
                mt=e.attrib.get('media-type','')
                if mt in ('application/xhtml+xml','text/html','text/xhtml'):
                    ii,hr=e.attrib.get('id',''),e.attrib.get('href','')
                    if ii and hr: mf[ii]=hr
        sp=[]
        for e in opf_root.iter():
            if e.tag.endswith('}itemref') or e.tag=='itemref':
                ir=e.attrib.get('idref','')
                if ir in mf: sp.append(ir)
        if not sp: raise ValueError(f"Empty spine: {opf_path}")
        bl=[]
        for ir in sp:
            hr=mf[ir]; fp=(od+'/'+hr).lstrip('/') if od else hr
            for c in (fp,hr):
                try: ct=zf.read(c).decode('utf-8',errors='replace'); break
                except KeyError: continue
            else: continue
            ex=_XHTMLTextExtractor(); ex.feed(ct); bl.extend(ex.get_blocks())
    return '\n\n'.join(bl)

def clean_hathitrust(text):
    """Full HathiTrust flat-stream OCR cleaning pipeline."""
    lines = text.split('\n')
    start = 0
    for i, line in enumerate(lines):
        if re.match(r'^##\s+p\.\s+\d+', line.strip()):
            start = i; break
    out = []
    skip_next = False
    for line in lines[start:]:
        if skip_next:
            skip_next = False; continue
        s = line.strip()
        if re.match(r'^##\s+p\.\s+\d+', s):
            skip_next = True; continue
        if re.match(r'^\d{1,3}$', s): continue
        if re.match(r'^[-—]{1,10}$', s): continue
        out.append(line)
    text = '\n'.join(out)
    text = re.sub(r'\$\s*(\d+)', r'§ \1', text)
    text = re.sub(r'(\w)- (\w)', r'\1\2', text)
    text = re.sub(r'[а-яА-ЯёЁ]{3,}[^\n]*\n', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    raw_blocks = text.split('\n\n')
    joined = []
    for block in raw_blocks:
        block = block.strip()
        if not block: continue
        merged = ' '.join(l.strip() for l in block.split('\n') if l.strip())
        merged = re.sub(r'  +', ' ', merged)
        joined.append(merged)
    final = []
    for block in joined:
        if not block: continue
        if final and block[0].islower():
            final[-1] += ' ' + block
        elif final and block[0] in '.,;:)!?':
            final[-1] += ' ' + block
        else:
            final.append(block)
    full = ' '.join(final)
    full = re.sub(r'  +', ' ', full)
    all_nums = sorted(set(int(m.group(1)) for m in re.finditer(r'§\s*(\d+)', full)))
    if all_nums:
        runs = [[all_nums[0]]]
        for n in all_nums[1:]:
            if n - runs[-1][-1] <= 2:
                runs[-1].append(n)
            else:
                runs.append([n])
        section_nums = set(max(runs, key=len))
    else:
        section_nums = set()
    for n in section_nums:
        full = re.sub(
            r'([.;:!?\-—)\]]) (§ ' + str(n) + r'[.\s])',
            r'\1\n\n\2', full)
    full = re.sub(r'([.;:!?\-—)\]]) (Anmerkung\.\s+(?:\d+\)\s+)?[A-ZÄÖÜWDSEI])', r'\1\n\n\2', full)
    # Use corrected Roman numeral pattern
    full = re.sub(r'([.;:!?\-—)\]]) ((?:' + _ROMAN_PAT + r')\.\s+[A-ZÄÖÜ]{3,})', r'\1\n\n\2', full)
    full = re.sub(r'([.;:!?\-—)\]]) ([A-Z]\.\s+[A-ZÄÖÜ]{3,}[A-ZÄÖÜ .]{5,})', r'\1\n\n\2', full)
    for n in section_nums:
        full = re.sub(r'(§\s*' + str(n) + r'\.?)\n\n', r'\1 ', full)
    paragraphs = [p.strip() for p in full.split('\n\n') if p.strip()]
    merged = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        if (p == p.upper() and len(p) < 100 and i + 1 < len(paragraphs)
                and paragraphs[i+1] == paragraphs[i+1].upper() and len(paragraphs[i+1]) < 100):
            merged.append(p + ' ' + paragraphs[i+1])
            i += 2
        else:
            merged.append(p)
            i += 1
    paragraphs = merged
    merged2 = []
    for p in paragraphs:
        if p.startswith('(') and merged2 and len(merged2[-1]) < 120:
            merged2[-1] += ' ' + p
        else:
            merged2.append(p)
    paragraphs = merged2
    for i in range(len(paragraphs)):
        paragraphs[i] = re.sub(r'(\w)- (\w)', r'\1\2', paragraphs[i])
    return '\n\n'.join(paragraphs)

_ABBREV_RE = re.compile(
    r'\b(?:z\s*\.\s*[Bb]|d\s*\.\s*[hiHI]|d\s*\.\s*i|u\s*\.\s*a|usw|vgl|'
    r'ebd|Anm|Bd|Bde|Nr|Dr|Prof|St|bzw|bes|evtl|ca|etc|ff|Kap|Hrsg|hg|Jg|'
    r'Jhdt|usf|sog|e\s*\.\s*g|i\s*\.\s*e|cf|op|cit|ibid|loc|vol|ed|pp|'
    r'nos?|vs|ext|approx|mgr|sr|jr|rev|col|gen|lt|sgt|capt|p|S|Tab|Abb|'
    r'Fig|fig)\s*\.$', re.IGNORECASE)

_MARGINAL_RE = re.compile(r'^([A-ZÄÖÜÀ-Þ][^—–]{1,60}?)\.\s?[—–-]\s')
_TITLE_STOP = {'der','die','das','des','dem','den','als','von','vom','und','zu','zur','zum','im','in','am','an','auf','durch','für','of','the','a','an','and','as','de','del','la','le','les','du','des','y','e','et','di','da'}

def clean_book_ocr(text, header_min=3):
    """Clean a scanned-book OCR export (PDFgear, ABBYY, Tesseract, Acrobat):
    one line per printed line, no blank lines between paragraphs, page folios,
    running headers and printer's signature marks interleaved.
    - drops standalone numbers, lines that recur >= header_min times (running
      headers) and near-duplicates of them (garbled headers), and '- Author, Title'
      signature lines
    - joins wrapped lines and end-of-line hyphenation (kept when the next line is
      capitalised, e.g. 'Rot-Weiß')
    - starts a new paragraph when the previous line is short (< median-9 chars)
      and ends a sentence, or when a line opens with a marginal title
      ('Heraklit. — ...'), which the short-line rule alone misses
    - merges leading ALL-CAPS title lines into one Title-Case heading line
    Returns blank-line-delimited paragraphs."""
    import difflib
    from collections import Counter
    lines = [l.strip() for l in text.split('\n')]
    counts = Counter(l for l in lines if l and len(l) < 80)
    headers = {l for l, c in counts.items() if c >= header_min and not re.search(r'[.!?:;,]$', l)}
    def is_header(l):
        if l in headers: return True
        if len(l) < 80 and not re.search(r'[.!?:;,]$', l):
            return any(difflib.SequenceMatcher(None, l, h).ratio() >= 0.8 for h in headers)
        return False
    body = []
    for l in lines:
        if not l: continue
        if re.fullmatch(r'\d{1,4}', l): continue
        if re.fullmatch(r'-\s*[A-ZÄÖÜÀ-Þ]\w+,\s.{3,50}', l): continue
        if is_header(l): continue
        body.append(l)
    k = 0
    while k < len(body) and body[k].isupper() and len(body[k]) < 80: k += 1
    title = []
    if k:
        t = body[0].title() + (': ' + ' '.join(x.title() for x in body[1:k]) if k > 1 else '')
        title = [t]
    body = body[k:]
    lens = sorted(len(b) for b in body); med = lens[len(lens)//2] if lens else 60
    th = med - 9
    END = re.compile(r'[.!?"“”»)\]]$'); START = re.compile(r'[A-ZÄÖÜÀ-Þ„“«]|"[A-ZÄÖÜÀ-Þ]')
    def titlelike(m):
        w = m.group(1).split()
        return 2 <= len(w) <= 6 and all(x[:1].isupper() or x.lower() in _TITLE_STOP for x in w)
    paras, cur = [], []
    for i, l in enumerate(body):
        if cur:
            prev = body[i-1]
            short = len(prev) < th and END.search(prev) and START.match(l)
            m = _MARGINAL_RE.match(l)
            # single-word name after a line ending in OCR garbage ('gewoben hat -', 'werden/*')
            single = m and len(m.group(1).split()) == 1 and re.search(r'[^\w\s.!?"“”»)\]]$', prev)
            marg = m and (END.search(prev) or titlelike(m) or single)
            if short or marg: paras.append(cur); cur = []
        cur.append(l)
    if cur: paras.append(cur)
    # warn about running headers the OCR spliced into a wrapped line at a page break
    long_h = [h for h in headers if len(h) >= 15]
    for pi, p in enumerate(paras, start=len(title)):
        for l in p:
            if len(l) > med + 20:
                for h in long_h:
                    mt = difflib.SequenceMatcher(None, l, h).find_longest_match(0, len(l), 0, len(h))
                    if mt.size >= 0.6 * len(h):
                        print(f"  [!] paragraph {pi}: possible spliced running header: …{l[max(0,mt.a-20):mt.a+mt.size+10]}…"); break
    def join(ls):
        out = ''
        for l in ls:
            if out.endswith('-') and not out.endswith(' -') and l[:1].islower(): out = out[:-1] + l
            else: out = (out + ' ' + l) if out else l
        return re.sub(r'(?<=[a-zäöüß])» (?=[a-zäöüß])', ', ', out)
    return '\n\n'.join(title + [join(p) for p in paras])

def detect_paragraphs(text):
    lines=text.split('\n'); out=[]
    for i,line in enumerate(lines):
        out.append(line)
        if i+1>=len(lines): continue
        s,nxt=line.rstrip(),lines[i+1].strip()
        if not s or not nxt: continue
        ends=bool(re.search(r'[.!?]["\'\)\]»]*$',s))
        if ends and _ABBREV_RE.search(s): ends=False
        starts=bool(re.match(r'[A-ZÄÖÜÀÁÂÃÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕØÙÚÛÜÝÞ"„"]',nxt)
                     or re.match(r'\d{1,2}\.\s+[A-ZÄÖÜ]',nxt))
        if ends and starts: out.append('')
    return '\n'.join(out)

def split_into_blocks(text): return [b.strip() for b in re.split(r'\n\s*\n',text) if b.strip()]

_PM_RE = [re.compile(p) for p in [
    r'^\d{1,4}\s+[A-ZÀ-ÞÄÖÜÑ][A-ZÀ-ÞÄÖÜÑ ]{0,29}$',
    r'^[A-ZÀ-ÞÄÖÜÑ][A-ZÀ-ÞÄÖÜÑ ]{0,29}\s+\d{1,4}$',
    r'^\d{1,4}$', r'^\[\d{1,4}(?:-\d{1,4})?\]$']]

def is_page_marker(block):
    lines=block.split('\n')
    if len(lines)!=1 or len(lines[0])>=40: return None
    ln=lines[0].strip()
    if _PM_RE[3].match(ln): return ln[1:-1]
    if any(_PM_RE[i].match(ln) for i in range(3)):
        m=re.search(r'\d{1,4}',ln); return m.group() if m else None
    return None

def _ends_mid(t): return not bool(re.search(r'[.!?…"\'»"]\s*$',t.rstrip()))
def _starts_mid(t): return t.lstrip()[:1].islower()

def clean_paragraph(text):
    text=re.sub(r'(\w)-\n(\w)',r'\1\2',text)
    lines=text.split('\n'); r=[]
    for line in lines:
        s=line.strip()
        if not s: continue
        if r:
            if not re.search(r'[.!?:»"\')\]]\s*$',r[-1]): r[-1]+=' '+s
            else: r.append(s)
        else: r.append(s)
    return '\n'.join(r)

def strip_page_markers(blocks):
    cl,ma,mm=[],{},{}; i=0
    while i<len(blocks):
        pn=is_page_marker(blocks[i])
        if pn is None: cl.append(clean_paragraph(blocks[i])); i+=1; continue
        nxt=blocks[i+1] if i+1<len(blocks) else ''
        pm=_ends_mid(cl[-1]) if cl else False
        nm=_starts_mid(nxt) if nxt else False
        if pm and nm and cl:
            prev=cl.pop(); nc=clean_paragraph(nxt)
            merged=(prev[:-1]+nc) if prev.endswith('-') and nc[:1].islower() else prev+' '+nc
            off=len(prev.rstrip())-1 if prev.rstrip().endswith('-') else len(prev.rstrip())
            cl.append(merged); mm.setdefault(len(cl)-1,[]).append((pn,off)); i+=2
        else:
            if cl: ma.setdefault(len(cl)-1,[]).append(pn)
            i+=1
    return cl,ma,mm

_MD_REPORTS={}   # side → md_prep report of the last .md read (heading levels, dropped lines)
_INLINE_MARK_RE=re.compile(r'\[(?:p\.\s*)?(?:\d{1,4}[a-z]?|[ivxlc]{1,6})(?:[-–]\d{1,4})?\]')

def _read_src(path,detect=False,hathitrust=False,side='orig'):
    if path.suffix.lower()=='.epub':
        print(f"  EPUB: {path.name}"); return extract_epub_text(path)
    t=path.read_text(encoding='utf-8')
    if path.suffix.lower() in MD_SUFFIXES:
        from md_prep import normalize_md, summary
        t,rep=normalize_md(t,side=side); _MD_REPORTS[side]=rep; print(summary(rep,path.name)); return t
    if hathitrust:
        return clean_hathitrust(t)
    return detect_paragraphs(t) if detect else t

def propagate_markers(pairs):
    """A translation that carries no inline page marker at all gets the original's markers copied in
    at the proportional word, so the HTML and the PDF show [n] in both columns and --verify passes.
    Returns the number of markers copied; 0 when the translation already has markers of its own
    (a translator's hand-placed markers are always better than proportional ones)."""
    if any(_INLINE_MARK_RE.search(p['trans']) for p in pairs): return 0
    n=0
    for p in pairs:
        o=p['orig']; ms=list(_INLINE_MARK_RE.finditer(o))
        if not ms: continue
        t=p['trans']; body=len(_INLINE_MARK_RE.sub('',o)) or 1; removed=0; ins=[]
        for m in ms:
            ins.append((round(len(t)*(m.start()-removed)/body), m.group())); removed+=m.end()-m.start()
        for pos,mk in sorted(ins,reverse=True):
            if pos<=0 or not t.strip(): t=(mk+' '+t.lstrip()).strip(); continue
            if pos>=len(t): t=t.rstrip()+' '+mk; continue
            b=pos
            if t[b]!=' ':
                l,h=t.rfind(' ',0,b),t.find(' ',b)
                b=l if (h<0 or (l>=0 and b-l<=h-b)) else h
                if b<0: b=len(t)
            t=(t[:b].rstrip()+' '+mk+' '+t[b:].lstrip()).strip()
        p['trans']=t; n+=len(ms)
    if n: print(f"  {n} page markers copied from the original into the translation at the proportional word")
    return n

def _attach_md_levels(pairs):
    """Markdown original: remember the `#` depth of each heading pair as md_level (1–6)."""
    lv=_MD_REPORTS.get('orig',{}).get('levels') or {}
    if not lv: return
    for p in pairs:
        l=lv.get(p['orig'].strip())
        if l: p['md_level']=l

def build_pairs(op,tp,do_detect=False,hathitrust=False,propagate=True):
    ob,tb=split_into_blocks(_read_src(op,do_detect,hathitrust=hathitrust)),split_into_blocks(_read_src(tp,side='trans'))
    oc,ma,mm=strip_page_markers(ob)
    tc=[clean_paragraph(b) for b in tb]
    if len(oc)!=len(tc):
        no,nt=len(oc),len(tc)
        print(f"\n  [!] Mismatch: orig={no}, trans={nt}")
        r=max(no,nt)/max(min(no,nt),1)
        if abs(r-round(r))<.12:
            print(f"  Hint: ratio ~{round(r)}:1 — {'orig' if no>nt else 'trans'} likely has standalone markers")
        for lbl,lst in [("orig",oc[:3]),("trans",tc[:3])]:
            for j,p in enumerate(lst):
                print(f"  {lbl}[{j}] {p[:100].replace(chr(10),' ')}{'…' if len(p)>100 else ''}")
        sys.exit(1)
    pairs=[]
    for i in range(len(oc)):
        p={"orig":oc[i],"trans":tc[i]}
        if i in mm: pn,off=mm[i][0]; p["page_mid"]=pn; p["mid_offset"]=off
        if i in ma: p["page_after"]=ma[i]
        pairs.append(p)
    _attach_md_levels(pairs)
    if propagate: propagate_markers(pairs)
    return pairs

# ── Anchor-based alignment verification ──────────────────────────────────────

def verify_alignment(pairs):
    """Check that structurally significant paragraphs are aligned.

    Returns (ok: bool, issues: list[str]).
    Checks:
      1. Roman-numeral chapter headings appear at the same index in both columns
      2. Numbered footnotes (N) ...) match between orig and trans
      3. Appendix / Anhang markers align
    """
    issues = []
    for i, p in enumerate(pairs):
        o, t = p['orig'], p['trans']
        # Chapter headings
        om = _ROMAN_RE.match(o)
        tm = _ROMAN_RE.match(t)
        if om and not tm:
            issues.append(f"  [{i}] orig has chapter '{om.group(1)}.' but trans starts: {t[:60]}")
        elif tm and not om:
            issues.append(f"  [{i}] trans has chapter '{tm.group(1)}.' but orig starts: {o[:60]}")
        elif om and tm and om.group(1) != tm.group(1):
            issues.append(f"  [{i}] chapter mismatch: orig='{om.group(1)}.' trans='{tm.group(1)}.'")

        # Page markers written inline ([12], [p. 12], [vii]) must be the same set on both sides
        omk=re.findall(r'\[(?:p\.\s*)?(?:\d{1,4}[a-z]?|[ivxlc]{1,6})(?:[-–]\d{1,4})?\]',o); tmk=re.findall(r'\[(?:p\.\s*)?(?:\d{1,4}[a-z]?|[ivxlc]{1,6})(?:[-–]\d{1,4})?\]',t)
        if omk!=tmk: issues.append(f"  [{i}] page markers differ: orig={omk} trans={tmk}")
        # A short ALL-CAPS heading on one side must be a short ALL-CAPS heading on the other (TOC and isH() need both)
        oc=_MARK_LEAD_RE.sub('',o); tc_=_MARK_LEAD_RE.sub('',t)
        ocaps=len(oc)<120 and oc==oc.upper() and sum(c.isalpha() for c in oc)>=3; tcaps=len(tc_)<120 and tc_==tc_.upper() and sum(c.isalpha() for c in tc_)>=3
        if ocaps!=tcaps: issues.append(f"  [{i}] heading case differs: orig={oc[:50]!r} trans={tc_[:50]!r}")
        # Numbered footnotes: N)
        ofn = re.match(r'^(\d+)\)', o)
        tfn = re.match(r'^(\d+)\)', t)
        if ofn and tfn and ofn.group(1) != tfn.group(1):
            issues.append(f"  [{i}] footnote mismatch: orig={ofn.group(1)}) trans={tfn.group(1)})")
        elif ofn and not tfn:
            issues.append(f"  [{i}] orig has footnote {ofn.group(1)}) but trans starts: {t[:50]}")
        elif tfn and not ofn:
            issues.append(f"  [{i}] trans has footnote {tfn.group(1)}) but orig starts: {o[:50]}")

        # Anhang / Appendix
        if re.match(r'^Anhang\b', o) and not re.match(r'^(?:Appendix|Anhang)\b', t, re.I):
            issues.append(f"  [{i}] orig='Anhang' but trans starts: {t[:50]}")

    ok = len(issues) == 0
    return ok, issues

def pairs_to_compact(pairs):
    """Convert pairs to positional arrays to reduce JSON size and V8 object overhead."""
    out = []
    for p in pairs:
        o, t = p['orig'], p['trans']
        pm  = p.get('page_mid')
        off = p.get('mid_offset')
        pa  = p.get('page_after')
        if pm is None and pa is None:
            out.append([o, t])
        elif pm is not None and pa is None:
            out.append([o, t, pm, off])
        elif pm is None and pa is not None:
            out.append([o, t, None, None, pa])
        else:
            out.append([o, t, pm, off, pa])
    return out

# ── JS helpers ───────────────────────────────────────────────────────────────
_JS_CORE = r"""var LS={g:function(k,f){try{var v=localStorage.getItem(k);return v===null?f:v}catch(e){return f}},s:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
function PM(n){var s=document.createElement('span');s.className='page-mark';s.textContent=' ['+n+'] ';return s}
function E(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\[(\d+)\]/g,'<span class="pg">[$1]</span>').replace(/\n/g,'</p><p>')}
function FC(el,t,mk,off){if(mk!==void 0){var p=document.createElement('p');p.append(t.slice(0,off),mk,t.slice(off));el.appendChild(p);return}el.innerHTML='<p>'+E(t)+'</p>'}
function isH(s){s=s.replace(/^\s*(?:\[[^\]]{1,8}\]\s*)+/,'');return s.length<120&&s===s.toUpperCase()&&/[A-ZÁÉÍÓÚÑÜ]/.test(s)}
function SW(t,p){if(p<=0)return 0;if(p>=t.length)return t.length;if(t[p]===' ')return p;var l=p-1,h=p+1;while(l>0&&t[l]!==' ')l--;while(h<t.length&&t[h]!==' ')h++;return(p-l<=h-p)?l:h}"""

# ── Immediate renderer (no lazy loading) ─────────────────────────────────────
_JS_RENDER_ENGINE = r"""
function _row(d,ai){
  var anc=document.createElement('div');anc.id='a'+ai;
  if(isH(d[0])){
    anc.className='section-div';
    var so=document.createElement('div'),st=document.createElement('div');
    so.className='s-orig';st.className='s-trans';
    if(window._LL)so.lang=window._LL;if(window._LR)st.lang=window._LR;
    so.textContent=d[0];st.textContent=d[1];
    anc.appendChild(so);anc.appendChild(st);
  }else{
    var row=document.createElement('div');row.className='row';
    var oc=document.createElement('div'),tc=document.createElement('div');
    oc.className='col';tc.className='col';
    if(window._LL)oc.lang=window._LL;if(window._LR)tc.lang=window._LR;
    if(d[2]!=null){
      FC(oc,d[0],PM(d[2]),d[3]);
      FC(tc,d[1],PM(d[2]),SW(d[1],Math.round(d[1].length*d[3]/Math.max(d[0].length,1))));
    }else{FC(oc,d[0]);FC(tc,d[1]);}
    row.appendChild(oc);row.appendChild(tc);anc.appendChild(row);
    if(d[4]){(Array.isArray(d[4])?d[4]:[d[4]]).forEach(function(n){
      container.insertAdjacentHTML('beforeend','<div class="page-row"><span class="page-mark"> ['+n+'] </span></div>')});}
  }
  container.appendChild(anc);
}
for(var _i=0;_i<DATA.length;_i++) _row(DATA[_i],_i);
"""

def _toc_blocks(include, chapters='roman', toc_kind=None):
    if not include: return '','','','',''
    css = """
.toc-nav{position:fixed;left:0;top:0;bottom:0;width:230px;background:var(--toc-bg);border-right:1px solid var(--rule);overflow-y:auto;overflow-x:hidden;z-index:200;display:flex;flex-direction:column;padding:0 0 2rem}
.toc-nav::-webkit-scrollbar{width:4px}.toc-nav::-webkit-scrollbar-thumb{background:var(--rule);border-radius:2px}
.toc-title{padding:1.2rem 1rem .8rem;font-family:var(--sans);font-size:9px;font-weight:600;letter-spacing:.25em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--rule);flex-shrink:0}
.tc0,.tc1,.tc2{display:block;font-family:var(--serif);color:var(--muted);text-decoration:none;border-left:2.5px solid transparent;transition:color .15s,border-color .15s;cursor:pointer;position:relative;padding-right:2.2rem}
.tc0{padding:.65rem 1rem .4rem;font-family:var(--sans);font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--text);margin-top:.5rem;line-height:1.3}
.tc1{padding:.3rem 1rem .25rem;font-size:12px;line-height:1.35}
.tc2{padding:.12rem 1rem .12rem 1.7rem;font-size:10.5px;line-height:1.3;opacity:.75}
.tc0:hover,.tc1:hover,.tc2:hover{color:var(--text)}
.tc0.active,.tc1.active,.tc2.active{color:var(--accent);border-left-color:var(--accent)}.tc1.active{font-weight:500}.tc2.active{opacity:1;font-weight:500}
.tp{position:absolute;right:.7rem;top:50%;transform:translateY(-50%);font-family:var(--sans);font-size:8.5px;opacity:.45}
@media(max-width:860px){.toc-nav{display:none}.toc-nav.open{display:flex;width:min(80vw,300px);box-shadow:0 0 24px rgba(0,0,0,.25)}#mB{display:flex!important}.page-wrap{margin-left:0!important}}
"""
    html = '<nav class="toc-nav" id="toc"><div class="toc-title">Contents</div></nav>'
    # TOC detection + scroll-spy: 3-level hierarchy (tc0=chapter, tc1=section, tc2=subsection)
    # Detects: ALL-CAPS headings, Roman numerals, keywords (Appendix/Preface/Einleitung/Kapitel/Teil),
    # § sections, Arabic-numbered headings, marginal run-in titles, a)-z) subsection labels.
    js = "var _CH='%s';var _TK=%s;" % (chapters, json.dumps({str(k):v for k,v in (toc_kind or {}).items()})) + r"""
var _MK=/^\s*(?:\[[^\]]{1,8}\]\s*)+/;
function tcs(s){if(s!==s.toUpperCase())return s;var S={of:1,the:1,a:1,an:1,and:1,as:1,to:1,in:1,on:1,for:1,with:1,from:1,de:1,del:1,la:1,el:1,los:1,las:1,y:1,e:1,en:1,por:1,con:1,der:1,die:1,das:1,und:1,von:1,zu:1,im:1,des:1,dem:1,den:1,du:1,le:1,les:1,et:1,di:1,il:1};var w=s.toLowerCase().split(' '),o=[],first=true;for(var i=0;i<w.length;i++){var x=w[i];if(/^([ivxlc]{1,6}|\d{1,3}|[a-z])[.)]?\*{0,3}$/.test(x)&&(i===0||/^[ivxlc]/.test(x))){o.push(/^[ivxlc]/.test(x)?x.toUpperCase():x);first=(i===0);continue}var cw=x.replace(/^[^\p{L}]+/u,''),op=/^[“"'(\[«]/.test(x);o.push((!first&&!op&&S[cw])?x:x.replace(/^([^\p{L}]*)(\p{L})/u,function(_,a,b){return a+b.toUpperCase()}));first=false}return o.join(' ')}
function dTE(o,t){
  o=o.replace(_MK,'');t=t.replace(_MK,'');
  var RM=/^(XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.\s+(.+?)\.?\s*$/;
  // Roman-numeral headings, also when set in capitals: the numeral decides the level, the case only the display
  var cm=o.match(RM);
  if(cm&&o.length<=120){var e=t.match(RM);return{type:_CH==='roman'?'tc0':'tc1',en:cm[1]+'. '+tcs((e?e[2]:cm[2]).replace(/\.+$/,'').replace(/\s*\(\d+\)$/,''))}}
  // Arabic-numbered headings ("3. Title", "3 TITLE")
  var an=o.match(/^(\d{1,2})\.?\s+([A-ZÁÉÍÓÚÑÜÀÂÃÅÆÇÈÊËÌÎÏÐÒÔÕØÙÛÝÞ].{2,})/);
  if(an&&o.length<=120){var atn=t.match(/^\d{1,2}\.?\s+([A-Z].{2,})/);var ar=tcs((atn?atn[1]:an[2]).trim().replace(/\.+$/,'').replace(/\s*\(\d+\)$/,''));if(ar.length>90){var sp=ar.lastIndexOf(' ',90);ar=ar.slice(0,sp>10?sp:90)+'…'}return{type:_CH==='arabic'?'tc0':'tc1',en:an[1]+'. '+ar}}
  // § sections → tc1
  var s=o.match(/^§\s*(\d+)\.?\s+([^.]{3,})/);if(s){var ts=t.match(/^§\s*\d+\.?\s+([^.]{3,})/);var r=(ts?ts[1]:s[2]).trim().replace(/\.+$/,'');return{type:'tc1',en:'§ '+s[1]+'. '+(r.length>40?r.slice(0,40)+'…':r)}}
  // Keyword headings: Anhang/Appendix, Vorwort/Preface, Einleitung/Introduction, Kapitel, Teil
  if(/^(Anhang|Appendix|Apéndice)\.?\s*$/i.test(o.trim())){return{type:'tc0',en:/^(Appendix|Anhang|Apéndice)/i.test(t)?tcs(t.trim().replace(/\.$/,'')):'Appendix'}}
  if(/^(Vorwort|Preface|Foreword|Introduction|Einleitung|Conclusi[oó]n(es)?|Zwischenbetrachtung)\.?\s*$/i.test(o.trim())){return{type:'tc0',en:tcs(t.split(/[.!?\n]/)[0].trim()||o.trim())}}
  if(/^(ERSTES|ZWEITES|DRITTES|VIERTES|FÜNFTES)\s+KAPITEL/i.test(o)||/^(FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+(CHAPTER|SECTION)/i.test(o)){return{type:'tc0',en:t.length<80?t:o}}
  if(/^(Erster|Zweiter|Dritter|Vierter)\s+Teil/i.test(o)&&o.length<120){return{type:'tc0',en:t.split(/[.!?\n]/)[0].trim()||o}}
  // Marginal run-in titles: "Heraklit. — …" → tc0 (label from the translation column)
  var mg=o.match(/^([A-ZÄÖÜÀ-Þ][^—–]{1,60}?)\.\s[—–-]\s/);if(mg){var mt=t.match(/^([A-Z][^—–]{1,80}?)\.\s[—–-]\s/);return{type:'tc0',en:(mt?mt[1]:mg[1]).trim()}}
  // a)-z) subsection labels → tc2 (short headings only, <120 chars)
  var sub=o.match(/^([a-zα-ω])\)\s+(.+)/);if(sub&&o.length<120){var st=t.match(/^(?:[a-zα-ω])\)\s+(.+)/);var sl=(st?st[1]:sub[2]).trim().replace(/\.+$/,'');if(sl.length>50){var sp2=sl.lastIndexOf(' ',50);sl=sl.slice(0,sp2>10?sp2:50)+'…'}return{type:'tc2',en:sub[1]+') '+sl}}
  // Unnumbered ALL-CAPS short paragraphs → tc0 (chapter level); isH() renders them as dividers too
  if(o.length<120&&o===o.toUpperCase()&&/[A-ZÁÉÍÓÚÑÜ]/.test(o)){return{type:'tc0',en:t.length<120?tcs(t):tcs(o)}}
  return null
}
var TN=document.getElementById('toc');
var TE=[];
DATA.forEach(function(d,i){var te=dTE(d[0],d[1]);var k=_TK[i];if(k!==undefined){if(k==='none')te=null;else{if(!te){var s0=d[1].replace(_MK,'');te={en:tcs(s0.length<120?s0:d[0].replace(_MK,''))}}te.type=k}}if(te)TE.push({id:'a'+i,dataIdx:i,e:te})});
if(TN&&TE.length){
  TE.forEach(function(entry){
    var a=document.createElement('a');a.href='#'+entry.id;
    a.className=entry.e.type;
    a.setAttribute('data-target',entry.id);
    a.textContent=entry.e.en;
    a.onclick=function(ev){
      ev.preventDefault();
      document.getElementById(entry.id).scrollIntoView({behavior:'smooth',block:'start'});
    };
    TN.appendChild(a);
  });
  // Scroll-spy: rAF-throttled scroll listener
  var tocLinks=TN.querySelectorAll('a[data-target]');
  var targets=[];
  tocLinks.forEach(function(a){var el=document.getElementById(a.getAttribute('data-target'));if(el)targets.push({link:a,el:el})});
  var activeLink=null;
  function setActive(link){
    if(link===activeLink)return;
    if(activeLink)activeLink.classList.remove('active');
    activeLink=link;
    if(link){link.classList.add('active');var tr=TN.getBoundingClientRect(),lr=link.getBoundingClientRect();if(lr.top<tr.top+50||lr.bottom>tr.bottom-30)link.scrollIntoView({block:'nearest',behavior:'smooth'})}
  }
  function updateSpy(){
    var threshold=(window.scrollY||window.pageYOffset)+window.innerHeight*0.25;
    var best=null;
    for(var i=targets.length-1;i>=0;i--){if(targets[i].el.offsetTop<=threshold){best=targets[i].link;break}}
    setActive(best);
  }
  var ticking=false;
  window.addEventListener('scroll',function(){if(!ticking){requestAnimationFrame(function(){updateSpy();ticking=false});ticking=true}},{passive:true});
  updateSpy();
}
"""
    return css, html, js, '.page-wrap{margin-left:230px}'

def _build_standalone(dj, title, left, right, lang):
    la=f' lang="{html_module.escape(lang)}"' if lang else ''
    return f"""<!DOCTYPE html>
<html{la}><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--t:#1a1a1a;--m:#8a8a8a;--r:#d8d5cc;--rh:#b8b5ac;--bg:#fff;--sf:Palatino Linotype,Palatino,Book Antiqua,Georgia,'Times New Roman',serif;--ss:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--fs:16px}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--t:#e8e5df;--m:#7a7870;--r:#3a3730;--rh:#5a5750;--bg:#1c1b18}}}}
:root[data-theme=dark]{{--t:#e8e5df;--m:#7a7870;--r:#3a3730;--rh:#5a5750;--bg:#1c1b18}}
*{{box-sizing:border-box}}body{{margin:0;padding:3rem 1.5rem;background:var(--bg);color:var(--t)}}
.W{{max-width:1400px;margin:0 auto;font-family:var(--sf)}}.T{{text-align:center;margin-bottom:1.25rem;font-size:19px;letter-spacing:.04em}}
.fc{{display:flex;align-items:center;justify-content:center;gap:.6rem;margin-bottom:2rem;font-family:var(--ss)}}
.fc button{{width:28px;height:28px;border-radius:50%;border:1px solid var(--rh);background:0 0;color:var(--t);font-family:var(--ss);font-size:13px;line-height:1;cursor:pointer}}
.fc button:hover{{background:var(--r)}}.fc span{{font-size:12px;color:var(--m);min-width:2.4em;text-align:center}}
.ch{{display:flex;justify-content:space-between;margin-bottom:1.5rem;padding-bottom:.6rem;border-bottom:1px solid var(--rh)}}
.ch span{{width:48%;font-size:13px;font-style:italic;color:var(--m)}}
#P{{position:relative}}#P::before{{content:"";position:absolute;top:0;bottom:0;left:50%;width:1px;background:var(--rh)}}
.row{{display:flex;justify-content:space-between;padding:1rem 0}}.row .col{{width:48%}}
.row .col p{{margin:0 0 .85em;font-size:var(--fs);line-height:1.65}}.row .col p:last-child{{margin-bottom:0}}
.section-div{{display:flex;justify-content:space-between;margin-top:2rem}}.section-div div{{width:48%;font-family:var(--ss);font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--m);padding:.5rem 0;border-top:1.5px solid var(--m)}}
.page-row{{text-align:center;padding:.5rem 0}}.page-mark{{color:var(--m);font-size:12px;font-family:var(--ss)}}
.pg{{font-family:var(--ss);font-size:.7em;font-variant-numeric:tabular-nums;color:var(--m);opacity:.55;letter-spacing:.02em}}
@media(max-width:600px){{#P::before{{display:none}}.ch,.row,.section-div{{flex-direction:column;gap:.75rem}}.ch span,.row .col,.section-div div{{width:100%}}.row .col+.col{{padding-top:.75rem;border-top:1px dashed var(--r)}}}}
</style></head><body>
<div class="W"><div class="T">{title}</div>
<div class="fc"><button id="fd">A−</button><span id="fl">16px</span><button id="fu">A+</button></div>
<div class="ch"><span>{left}</span><span>{right}</span></div>
<div id="P"></div></div>
<script>
var DATA={dj},container=document.getElementById('P'),root=document.documentElement;
{_JS_CORE}
{_JS_RENDER_ENGINE}
var fz=parseInt(LS.g('sbs-fs','16'),10);fz=isFinite(fz)?Math.min(28,Math.max(12,fz)):16;
var fl=document.getElementById('fl');
function af(){{root.style.setProperty('--fs',fz+'px');fl.textContent=fz+'px';LS.s('sbs-fs',fz)}}
document.getElementById('fu').onclick=function(){{fz=Math.min(28,fz+1);af()}};
document.getElementById('fd').onclick=function(){{fz=Math.max(12,fz-1);af()}};
af();
</script></body></html>"""

def _build_artifact(dj, title, left, right, toc=False, chapters='roman', toc_kind=None, col_langs=None):
    tc,th,tj,pw_css = _toc_blocks(toc, chapters, toc_kind)
    ls_tag = ('<script>window._LL=%s;window._RL=0;window._LR=%s;</script>\n' % (json.dumps(col_langs[0]), json.dumps(col_langs[1]))) if col_langs else ''
    pw_o = '<div class="page-wrap">' if toc else ''
    pw_c = '</div>' if toc else ''
    return f"""<title>{title}</title>
{ls_tag}<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
:root{{--bg:#FAF8F5;--bg-alt:#F0EDE8;--toc-bg:#EDEAE5;--text:#2C2A26;--muted:#6A655B;--accent:#8B5E3C;--rule:#D5CFC5;--serif:"Cormorant Garamond","Palatino Linotype",Palatino,Georgia,serif;--sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--fs:16.5px;--lh:1.78}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1A1816;--bg-alt:#22201D;--toc-bg:#151311;--text:#E0DCD5;--muted:#8A8378;--accent:#C4946A;--rule:#3A3630}}}}
:root[data-theme="dark"]{{--bg:#1A1816;--bg-alt:#22201D;--toc-bg:#151311;--text:#E0DCD5;--muted:#8A8378;--accent:#C4946A;--rule:#3A3630}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--serif);line-height:var(--lh)}}
{pw_css}{tc}
.controls-bar{{position:fixed;top:0;right:0;z-index:300;display:flex;align-items:center;gap:8px;padding:8px 14px;background:var(--bg-alt);border-bottom-left-radius:8px;border-left:1px solid var(--rule);border-bottom:1px solid var(--rule);font-family:var(--sans);font-size:11px;color:var(--muted)}}
.controls-bar button{{background:none;border:1px solid var(--rule);border-radius:4px;width:30px;height:30px;cursor:pointer;color:var(--text);font-size:13px;font-family:var(--sans);font-weight:600;display:flex;align-items:center;justify-content:center;transition:background .12s,border-color .12s}}
.controls-bar button:hover{{background:var(--rule);border-color:var(--accent)}}
.size-val{{font-variant-numeric:tabular-nums;min-width:36px;text-align:center;font-weight:600}}
.ctrl-div{{width:1px;height:18px;background:var(--rule)}}
.masthead{{max-width:1100px;margin:0 auto;padding:3.5rem 1.5rem 0;text-align:center}}
.main-title{{font-family:var(--serif);font-size:clamp(1.4rem,3vw,2rem);font-weight:400;font-style:italic;line-height:1.3;letter-spacing:.01em;color:var(--text)}}
.subtitle{{font-family:var(--sans);font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:.6rem}}
.rule{{width:60px;height:1px;background:var(--accent);margin:1.8rem auto;opacity:.5}}
.col-bar{{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr;gap:2rem;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:.5rem 0;position:sticky;top:0;background:var(--bg);z-index:100}}
.col-label{{font-family:var(--sans);font-size:10px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);padding:0 1.5rem}}.col-label:last-child{{text-align:right}}
.paras{{max-width:1100px;margin:0 auto;position:relative}}
.paras::before{{content:'';position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--rule);pointer-events:none}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;padding:.65rem 0;border-bottom:1px solid transparent}}.row:hover{{border-bottom-color:var(--rule)}}
.row .col{{padding:0 1.5rem}}
.row .col p{{margin:0 0 .8em;font-size:var(--fs);line-height:var(--lh);hyphens:auto;text-align:justify;text-align-last:left}}.row .col p:last-child{{margin-bottom:0}}.row .col:last-child{{opacity:.88}}
.section-div{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;margin-top:2.4rem}}
.section-div .s-orig,.section-div .s-trans{{font-family:var(--sans);font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);padding:.55rem 1.5rem;border-top:1.5px solid var(--accent)}}
.page-row{{max-width:1100px;margin:0 auto;text-align:center;padding:.35rem 0}}.page-mark{{color:var(--muted);font-size:11px;font-family:var(--sans)}}
.pg{{font-family:var(--sans);font-size:.7em;font-variant-numeric:tabular-nums;color:var(--accent);opacity:.85;letter-spacing:.02em}}
.controls-bar button:focus-visible,.toc-nav a:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
#mB{{display:none}}
@media(min-width:861px){{.col-label:last-child{{padding-right:calc(1.5rem + 200px)}}}}
@media(max-width:640px){{.col-bar,.row,.section-div{{grid-template-columns:1fr;gap:0}}.paras::before{{display:none}}.row .col:first-child{{border-bottom:1px solid var(--rule);padding-bottom:.6rem;margin-bottom:.6rem}}.row .col:last-child{{opacity:1}}.col-bar{{display:none}}.section-div .s-trans{{border-top:none;padding-top:0}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{transition:none!important;animation:none!important}}}}
</style>
{th}
<div class="controls-bar">
  <button id="sizeDown" aria-label="Decrease text size">A−</button>
  <span class="size-val" id="sizeVal">100%</span>
  <button id="sizeUp" aria-label="Increase text size">A+</button>
  <span class="ctrl-div"></span>
  <button id="tB" aria-label="Toggle theme">☾</button>
</div>
{pw_o}<header class="masthead"><h1 class="main-title">{title}</h1>
<div class="rule"></div>
</header>
<div class="col-bar"><span class="col-label">{left}</span><span class="col-label">{right}</span></div>
<div class="paras" id="paras"></div>{pw_c}
<script>
var DATA={dj},container=document.getElementById('paras'),root=document.documentElement;
{_JS_CORE}
// Font size: stepped, percentage-based
var BASE=16.5,steps=[12,13.5,15,16.5,18,20,22,25],idx=3;
try{{var _s=localStorage.getItem('sbs-fsidx');if(_s!==null)idx=parseInt(_s,10)}}catch(e){{}}
if(isNaN(idx)||idx<0||idx>=steps.length)idx=3;
function applySize(){{root.style.setProperty('--fs',steps[idx]+'px');document.getElementById('sizeVal').textContent=Math.round(steps[idx]/BASE*100)+'%';try{{localStorage.setItem('sbs-fsidx',idx)}}catch(e){{}}}}
applySize();
document.getElementById('sizeDown').onclick=function(){{if(idx>0){{idx--;applySize()}}}};
document.getElementById('sizeUp').onclick=function(){{if(idx<steps.length-1){{idx++;applySize()}}}};
{_JS_RENDER_ENGINE}
{tj}
var dk;try{{var stored=localStorage.getItem('sbs-th');dk=stored==='dark'}}catch(e){{dk=false}}
if(!LS.g('sbs-th',null))dk=matchMedia('(prefers-color-scheme:dark)').matches;
var _cb=document.querySelector('.controls-bar'),_tn=document.querySelector('.toc-nav');if(_cb&&_tn){{var mb=document.createElement('button');mb.id='mB';mb.textContent='☰';mb.title='Contents';mb.setAttribute('aria-label','Toggle contents');mb.onclick=function(){{_tn.classList.toggle('open')}};_cb.insertBefore(mb,_cb.firstChild);_tn.addEventListener('click',function(e){{if(e.target.tagName==='A')_tn.classList.remove('open')}})}}
function aT(){{root.setAttribute('data-theme',dk?'dark':'light');document.getElementById('tB').textContent=dk?'☀':'☾';try{{localStorage.setItem('sbs-th',dk?'dark':'light')}}catch(e){{}}}}
aT();document.getElementById('tB').onclick=function(){{dk=!dk;aT()}};
</script>"""

def build_html(pairs, title, left_label, right_label, lang='', artifact=False, include_toc=False, chapters='roman', toc_kind=None):
    langs = [lang] if isinstance(lang, str) else list(lang or [])
    ll = langs[0] if langs else ''
    col = (langs[0], langs[1]) if len(langs) >= 2 else None
    compact = pairs_to_compact(pairs)
    dj = json.dumps(compact, ensure_ascii=False).replace('</', '<\\/')
    t,l,r = html_module.escape(title), html_module.escape(left_label), html_module.escape(right_label)
    return _build_artifact(dj,t,l,r,include_toc,chapters,toc_kind,col) if artifact else _build_standalone(dj,t,l,r,ll)

def _parse_toc_kind(specs):
    tk={}
    for spec in specs or []:
        i,_,k=spec.partition('='); k=k.strip()
        if not i.strip().isdigit() or k not in ('tc0','tc1','tc2','none'): sys.exit(f'  [!] --toc-kind expects IDX=tc0|tc1|tc2|none, got {spec!r}')
        tk[int(i)]=k
    return tk

def _slug(title):
    return re.sub(r'[\s_]+','-',re.sub(r'[^\w\s-]','',title.lower())).strip('-') or 'side-by-side'

def main():
    ap=argparse.ArgumentParser(description="Side-by-side parallel text HTML (v4).")
    ap.add_argument("original"); ap.add_argument("translation")
    ap.add_argument("-o","--output",default=None); ap.add_argument("--title",default=None)
    ap.add_argument("--left-label",default="Original"); ap.add_argument("--right-label",default="Translation")
    ap.add_argument("--lang",nargs="+",default=[],help="BCP-47 code(s): one for the standalone html lang, two (L R) to stamp lang on the original and translation columns, e.g. --lang es en"); ap.add_argument("--artifact",action="store_true")
    ap.add_argument("--toc",action="store_true"); ap.add_argument("--json-only",action="store_true")
    ap.add_argument("--count",action="store_true"); ap.add_argument("--detect-paragraphs",action="store_true")
    ap.add_argument("--hathitrust",action="store_true")
    ap.add_argument("--hathitrust-prep",action="store_true",help="Clean HathiTrust OCR original, write to -o, and exit")
    ap.add_argument("--book-ocr-prep",action="store_true",help="Clean a scanned-book OCR export (page numbers, running headers, no blank lines), write paragraphs to -o, and exit")
    ap.add_argument("--html-copy",default=None,help="Also write a full standalone HTML document (doctype/head/body around the artifact fragment) to this path, e.g. ~/Desktop/Title.html")
    ap.add_argument("--toc-debug",action="store_true")
    ap.add_argument("--toc-chapters",choices=["roman","arabic"],default="roman",help="Which numbered headings are top-level in the TOC (default roman; use arabic for essay collections numbered 1., 2., …)")
    ap.add_argument("--verify",action="store_true",help="Anchor-based alignment check (chapters, footnotes)")
    ap.add_argument("--toc-kind",action="append",metavar="IDX=tc0|tc1|tc2|none",help="(with --toc) force the TOC level of one pair, or drop it with none; e.g. --toc-kind 313=tc1 --toc-kind 274=tc1")
    ap.add_argument("--marginal-level",choices=["tc0","tc1","tc2","none"],default="tc0",help="(with --toc) sidebar level of run-in / marginal titles such as 'Heraklit. — …' (default tc0; tc2 nests them under the sections)")
    ap.add_argument("--front-matter",choices=["auto","keep"],default="auto",help="auto (default): of several heading pairs before the first body paragraph only the last enters the TOC")
    ap.add_argument("--md-dump",metavar="DIR",help="Markdown inputs: write the normalised orig.txt / trans.txt (exactly what the aligner sees) to DIR and exit — for inspection; keep editing the .md")
    ap.add_argument("--no-propagate-markers",action="store_true",help="do not copy the original's inline [n] page markers into a translation that carries none")
    a=ap.parse_args(); op,tp=Path(a.original),Path(a.translation)
    for p in (op,tp):
        if not p.exists(): print(f"  [!] Not found: {p}"); sys.exit(1)
    if a.md_dump:
        d=Path(a.md_dump).expanduser(); d.mkdir(parents=True,exist_ok=True)
        for p,side in ((op,'orig'),(tp,'trans')):
            (d/f'{side}.txt').write_text(_read_src(p,a.detect_paragraphs,hathitrust=(a.hathitrust and side=='orig'),side=side),encoding='utf-8')
        print(f"  → {d}/orig.txt, {d}/trans.txt (normalised copies; the builders redo this on every run — fix the .md, not these)\n"); sys.exit(0)
    if a.count or a.verify:
        oc,_,_=strip_page_markers(split_into_blocks(_read_src(op,a.detect_paragraphs,hathitrust=a.hathitrust)))
        tc=[clean_paragraph(b) for b in split_into_blocks(_read_src(tp,side='trans'))]
        ok=len(oc)==len(tc)
        print(f"\n  {op.name}: {len(oc)} paras | {tp.name}: {len(tc)} paras | {'✓' if ok else '✗ MISMATCH'}")
        if not ok:
            sys.exit(1)
        if a.verify:
            pairs = [{"orig":oc[i],"trans":tc[i]} for i in range(len(oc))]
            if not a.no_propagate_markers: propagate_markers(pairs)
            v_ok, issues = verify_alignment(pairs)
            if v_ok:
                print(f"  Alignment: ✓ all anchors match\n")
            else:
                print(f"  Alignment: ✗ {len(issues)} issue(s):")
                for iss in issues:
                    print(iss)
                print()
                sys.exit(1)
        else:
            print()
        sys.exit(0)
    if a.book_ocr_prep:
        cleaned=clean_book_ocr(op.read_text(encoding='utf-8'))
        paras=[p for p in cleaned.split('\n\n') if p.strip()]
        out=Path(a.output) if a.output else op.with_name('orig.txt')
        out.write_text(cleaned,encoding='utf-8')
        short=sum(1 for p in paras if len(p)<120)
        print(f"\n  Book OCR cleaned: {len(paras)} paragraphs ({short} under 120 chars) → {out}")
        print("  Spot-check with scripts/show_paras.py; fix the heading casing and any merged marginal titles with scripts/fix_orig.py.\n")
        sys.exit(0)
    if a.hathitrust_prep:
        raw=op.read_text(encoding='utf-8')
        cleaned=clean_hathitrust(raw)
        paras=[p.strip() for p in cleaned.split('\n\n') if p.strip()]
        out=Path(a.output) if a.output else op.with_name('orig.txt')
        out.write_text(cleaned,encoding='utf-8')
        print(f"\n  HathiTrust cleaned: {len(paras)} paragraphs → {out}\n")
        sys.exit(0)
    title=a.title or op.stem.replace('_',' ').replace('-',' ').title()
    print(f"\n  {op.name} + {tp.name}" + (f" [{('artifact+TOC' if a.toc else 'artifact') if a.artifact else 'json' if a.json_only else 'standalone'}]"))
    pairs=build_pairs(op,tp,do_detect=a.detect_paragraphs,hathitrust=a.hathitrust,propagate=not a.no_propagate_markers)
    npm=sum(1 for p in pairs if p.get('page_after') or p.get('page_mid'))
    # Markdown headings carry their `#` depth: # → tc0, ## → tc1, ### → tc2; an explicit --toc-kind still wins
    md_toc={i:f"tc{min(p['md_level'],3)-1}" for i,p in enumerate(pairs) if p.get('md_level')}
    if md_toc: print(f"  {len(md_toc)} Markdown headings set the TOC levels (override with --toc-kind IDX=…)")
    if a.marginal_level!="tc0":
        for i,p in enumerate(pairs):
            o=_MARK_LEAD_RE.sub('',p['orig'])
            if _MARGINAL_RE.match(o) and not (len(o)<120 and o==o.upper()): md_toc.setdefault(i,a.marginal_level)
    if a.front_matter=="auto":
        def _hd(p):
            o=_MARK_LEAD_RE.sub('',p['orig']); return bool(p.get('md_level')) or (len(o)<120 and o==o.upper() and sum(c.isalpha() for c in o)>=3)
        lead=0
        while lead<len(pairs) and _hd(pairs[lead]): lead+=1
        if lead>=2:
            for i in range(lead-1): md_toc[i]='none'
            print(f"  TOC: front-matter pair(s) 0–{lead-2} left out")
    print(f"  {len(pairs)} pairs" + (f", {npm} page markers" if npm else ''))

    # Always run verify on build
    v_ok, issues = verify_alignment(pairs)
    if not v_ok:
        print(f"\n  [!] Alignment issues ({len(issues)}):")
        for iss in issues:
            print(iss)
        print("  Run with --verify to diagnose. Continuing anyway…\n")

    if a.toc_debug:
        found=[]
        ch=a.toc_chapters; forced={**md_toc,**_parse_toc_kind(a.toc_kind)}
        for i,p in enumerate(pairs):
            o=_MARK_LEAD_RE.sub('',p['orig']); kind=None
            if _ROMAN_RE.match(o) and len(o)<=120: kind=('tc0' if ch=='roman' else 'tc1')+'(roman)'
            elif re.match(r'^\d{1,2}\.?\s+[A-ZÁÉÍÓÚÑÜÀÂÃÅÆÇÈÊËÌÎÏÐÒÔÕØÙÛÝÞ]',o) and len(o)<=120: kind=('tc0' if ch=='arabic' else 'tc1')+'(num)'
            elif re.match(r'^§\s*\d+',o): kind='tc1(§)'
            elif re.match(r'^(?:Anhang|Appendix|Apéndice)\b',o,re.IGNORECASE): kind='tc0(kw:appendix)'
            elif re.match(r'^(?:Vorwort|Preface|Foreword|Introduction|Einleitung|Conclusi[oó]n(?:es)?|Zwischenbetrachtung)',o,re.IGNORECASE) and len(o)<80: kind='tc0(kw)'
            elif re.match(r'^(ERSTES|ZWEITES|DRITTES|VIERTES|FÜNFTES)\s+KAPITEL',o,re.IGNORECASE): kind='tc0(kapitel)'
            elif re.match(r'^(Erster|Zweiter|Dritter|Vierter)\s+Teil',o,re.IGNORECASE): kind='tc0(teil)'
            elif _MARGINAL_RE.match(o): kind='tc0(marginal)'
            elif re.match(r'^[a-zα-ω]\)\s+',o) and len(o)<120: kind='tc2(sub)'
            elif len(o)<120 and o==o.upper() and sum(1 for c in o if c.isalpha() and c.isupper())>=2: kind='tc0(allcaps)'
            if i in forced: kind=f"{forced[i]}(forced{'' if kind is None else ' from '+kind})"
            if kind and not kind.startswith('none'): found.append(f"  [{i}] {kind}: {o[:70]}")
        if found:
            print(f"\n  TOC entries detected ({len(found)}):")
            for ln in found: print(ln)
        else: print("\n  TOC: no entries detected")
        print(); sys.exit(0)
    if a.json_only:
        out=Path(a.output) if a.output else op.with_name(op.stem+'_pairs.json')
        jt=json.dumps(pairs,ensure_ascii=False,indent=2)
        try: out.write_text(jt,encoding='utf-8')
        except OSError: out=Path.cwd()/out.name; out.write_text(jt,encoding='utf-8')
        print(f"  → {out}\n"); return
    result=build_html(pairs,title,a.left_label,a.right_label,lang=a.lang,artifact=a.artifact,include_toc=a.toc,chapters=a.toc_chapters,toc_kind={**md_toc,**_parse_toc_kind(a.toc_kind)})
    out=Path(a.output) if a.output else (Path.home()/'Desktop'/f"{_slug(title)}.html" if a.artifact else op.with_name(op.stem+'_side_by_side.html'))
    try: out.write_text(result,encoding='utf-8')
    except OSError: out=Path.cwd()/out.name; out.write_text(result,encoding='utf-8')
    print(f"  → {out}")
    if a.html_copy:
        full=('<!doctype html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>%s</title>\n<style>body{margin:0}</style>\n</head>\n<body>\n' % ((a.lang[0] if a.lang else 'en'), html_module.escape(title))) + result + '\n</body>\n</html>\n'
        cp=Path(a.html_copy).expanduser(); cp.write_text(full,encoding='utf-8')
        print(f"  → {cp} (standalone copy)")
    print()

if __name__=="__main__": main()
