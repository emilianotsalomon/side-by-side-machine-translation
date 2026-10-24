#!/usr/bin/env python3
"""build_pdf.py — print-ready parallel edition (PDF) of a side-by-side translation.

Companion to side_by_side_html.py: same inputs, same alignment, but a paginated PDF —
landscape letter, Cormorant Garamond, original left / translation right with paragraph
starts aligned across page breaks, a table of contents at the front (three heading
levels, with the source page in brackets and the PDF page), title block and running
head, the source's own notes set in smaller type, page markers kept inline as [n],
no line numbers.

    # from the aligned text files (preferred — same files the HTML was built from)
    python3 build_pdf.py orig.txt trans.txt --author "Ludwig Klages" \
        --work "Vom Wesen des Bewußtseins" --edition "the edition of 1921" \
        --lang de en -o ~/Desktop/Title.pdf

    # Markdown inputs work the same way (an OCR .md and an LLM translation .md): they are
    # normalised on load by md_prep.py — `#` headings keep their depth as the heading level,
    # [^n] notes become (n) notes, the translation's page blocks are dropped and the original's
    # [n] markers copied in. Refine by editing the .md files (fix_orig.py works on them).
    python3 build_pdf.py book.ocr.md translation.md --author … --work … --lang es en

    # from an existing side-by-side HTML (DATA array or .pair/.row markup)
    python3 build_pdf.py ~/Desktop/Title.html --author … --work … --lang de en

Use --inspect first: it lists what will become a heading (and at which level), a note,
or a run-in title, so you can correct it with --level / --kind before rendering.
Requires Google Chrome; poppler (pdfinfo/pdftoppm) is optional for checks and previews.
"""
from __future__ import annotations
import argparse, base64, html, json, os, re, shutil, subprocess, sys, time
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))

# ── type / page geometry (px at 96 dpi; the template's measurements assume 18 px lines) ──
FONT = {"family": "Cormorant Garamond", "weight": 500, "size": 15.5, "lh": 18,
        "files": {("normal", 500): "cormorantgaramond-medium.ttf", ("italic", 500): "cormorantgaramond-mediumitalic.ttf",
                  ("normal", 700): "cormorantgaramond-bold.ttf", ("italic", 700): "cormorantgaramond-bolditalic.ttf"}}
PAPER = {"letter": (1056, 816), "a4": (1123, 794)}
LANG_NAME = {"de": "German", "en": "English", "es": "Spanish", "fr": "French", "it": "Italian", "la": "Latin",
             "el": "Greek", "grc": "Greek", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian"}
TOC_TITLE = {"de": "Inhalt", "es": "Índice", "fr": "Table des matières", "it": "Indice", "la": "Index",
             "pt": "Índice", "nl": "Inhoud", "en": "Contents"}
ROMAN = r"(?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)"
MARK_RE = re.compile(r"\[(?:p\.\s*)?(?:[IV]{1,3}\.)?(?:\d{1,4}[a-z]?|[ivxlc]{1,6})(?:[-–]\d{1,4})?\]")   # [23] [p. 23] [xii] [I.23] (volume/part prefix)
STOP = {"der","die","das","des","dem","den","als","von","vom","und","zu","zur","zum","im","in","am","an","auf","durch","für","mit","oder",
        "of","the","a","an","and","as","to","in","on","for","with","from","toward","by","at","or","nor","but","de","del","la","el","los","las","y","e","en","por","con",
        "du","des","le","les","et","à","di","da","il","lo","gli","i"}
MARGINAL_RE = re.compile(r"^([A-ZÄÖÜÀ-Þ][^—–]{1,60}?)\.\s?[—–-]\s")
KIND_LEVEL = {"caps": 1, "kapitel": 1, "keyword": 1, "roman": 1, "section": 2, "arabic": 2, "letterdot": 2,
              "letterparen": 3, "greek": 3, "runin": 2}
FN_RE = re.compile(r"^\s*(?:\(\d{1,3}[a-c]?\)|\d{1,3}\)|\d{1,3}\s+(?=[^\d\s.,;)])|\*{1,3}\)?\s|[†‡•]\s?|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Inputs → pairs [{orig, trans, page_mid, mid_offset, page_after, heading}]
# ══════════════════════════════════════════════════════════════════════════════
def pairs_from_texts(op, tp, detect=False, propagate=True):
    import side_by_side_html as S
    pairs = S.build_pairs(op, tp, do_detect=detect, propagate=propagate)
    ok, issues = S.verify_alignment(pairs)
    if not ok:
        print(f"  [!] alignment issues ({len(issues)}) — the PDF will show them side by side:")
        for x in issues[:12]: print(x)
    return pairs


def _scan_js_array(src, start):
    depth = 0; i = start; n = len(src); q = None
    while i < n:
        c = src[i]
        if q:
            if c == "\\": i += 2; continue
            if c == q: q = None
        elif c in "\"'`": q = c
        elif c == "[": depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0: return src[start:i + 1]
        i += 1
    return None


def _js_to_json(text):
    try: return json.loads(text)
    except Exception: pass
    out = []; i = 0; n = len(text); code = []
    while i < n:
        c = text[i]
        if c in "\"'`":
            out.append(("c", "".join(code))); code = []; q = c; j = i + 1; buf = []
            while j < n and text[j] != q:
                if text[j] == "\\":
                    nxt = text[j + 1] if j + 1 < n else ""
                    if q != '"' and nxt == q: buf.append(q); j += 2; continue
                    buf.append(text[j:j + 2]); j += 2; continue
                if text[j] == "\n" and q == "`": buf.append("\\n"); j += 1; continue
                if text[j] == '"' and q != '"': buf.append('\\"'); j += 1; continue
                buf.append(text[j]); j += 1
            out.append(("s", '"' + "".join(buf) + '"')); i = j + 1
        else: code.append(c); i += 1
    out.append(("c", "".join(code)))
    def fix(s):
        s = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', s); s = re.sub(r",(\s*[\]}])", r"\1", s)
        return re.sub(r"\bundefined\b", "null", s)
    return json.loads("".join(fix(t) if k == "c" else t for k, t in out))


class _Dom(HTMLParser):
    VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "source"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#root", "attrs": {}, "children": [], "parent": None}; self.cur = self.root
    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": [], "parent": self.cur}
        self.cur["children"].append(node)
        if tag not in self.VOID: self.cur = node
    def handle_endtag(self, tag):
        n = self.cur
        while n and n["tag"] != tag: n = n["parent"]
        if n and n["parent"]: self.cur = n["parent"]
    def handle_data(self, data):
        if self.cur["tag"] in ("script", "style"): return
        self.cur["children"].append(data)


def _paras(node):
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "br"}
    out = []; buf = []
    def flush():
        t = re.sub(r"\s+", " ", "".join(buf)).strip()
        if t: out.append(t)
        buf.clear()
    def walk(n):
        if isinstance(n, str): buf.append(n); return
        if n["tag"] in BLOCK:
            flush(); [walk(c) for c in n["children"]]; flush(); return
        [walk(c) for c in n["children"]]
    [walk(c) for c in node["children"]]; flush()
    return out


def pairs_from_html(path):
    src = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?:const|let|var)\s+(DATA|PAIRS)\s*=\s*\[", src)
    if m:
        arr = _js_to_json(_scan_js_array(src, m.end() - 1)); pairs = []
        for el in arr:
            if isinstance(el, list):
                p = {"orig": el[0], "trans": el[1]}
                if len(el) > 3 and el[2] is not None: p["page_mid"] = el[2]; p["mid_offset"] = el[3]
                if len(el) > 4 and el[4]: p["page_after"] = el[4]
            else:
                p = {"orig": el.get("orig", ""), "trans": el.get("trans", "")}
                for k in ("page_mid", "mid_offset", "page_after"):
                    if el.get(k) is not None: p[k] = el[k]
                if el.get("folioBefore") or el.get("page_before"): p["page_before"] = el.get("folioBefore") or el.get("page_before")
            pairs.append(p)
        print(f"  pairs source: JS array {m.group(1)} ({len(pairs)})"); return pairs
    dom = _Dom(); dom.feed(src); pairs = []
    def visit(n):
        if isinstance(n, str): return
        cls = n["attrs"].get("class", "").split()
        if n["tag"] == "div" and cls and cls[0] in ("pair", "row", "parallel"):
            kids = [c for c in n["children"] if not isinstance(c, str)]
            if len(kids) >= 2:
                pairs.append({"orig": "\n".join(_paras(kids[0])), "trans": "\n".join(_paras(kids[1])),
                              "heading": ("chapter-pair" in cls) or None}); return
        if n["tag"] == "div" and "section-div" in cls:
            kids = [c for c in n["children"] if not isinstance(c, str)]
            if len(kids) >= 2:
                pairs.append({"orig": " ".join(_paras(kids[0])), "trans": " ".join(_paras(kids[1])), "heading": True}); return
        for c in n["children"]: visit(c)
    visit(dom.root)
    if not pairs: sys.exit("No DATA array and no .pair/.row markup found in the HTML.")
    print(f"  pairs source: DOM rows ({len(pairs)})"); return pairs


def html_meta(path):
    src = path.read_text(encoding="utf-8", errors="replace")
    t = re.search(r"<title>([^<]*)</title>", src); labels = re.findall(r'class="col-label">([^<]*)<', src)
    lang = re.search(r'<html[^>]*\blang="([a-zA-Z-]+)"', src)
    return (html.unescape(t.group(1)).strip() if t else ""), labels, (lang.group(1) if lang else None)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Classification
# ══════════════════════════════════════════════════════════════════════════════
def plain(s): return MARK_RE.sub("", s).strip()

def heading_kind(o, t, chapters="roman"):
    """→ (kind, display_paragraphs or None) for a standalone paragraph, else (None, None)."""
    s = plain(o); ts = plain(t)
    if not s or len(s) > 160 or len(ts) > 200: return None, None
    if s.endswith(("?", "!", ";", ",")) and not re.match(r"^[§$]", s): return None, None
    caps = s == s.upper() and sum(c.isalpha() for c in s) >= 3
    # Numbered headings first, even when set in capitals ("1. DISPOSICIÓN …", "II. EL TIEMPO …"):
    # the number decides the level; the capitals only decide the display case (see titlecase()).
    if re.match(r"^" + ROMAN + r"\.\s+\S", s) and len(s) <= 120: return ("roman" if chapters == "roman" else "arabic"), None
    if re.match(r"^\d{1,2}\.\s+[A-ZÄÖÜÁÉÍÓÚÑ„»\"]", s) and len(s) <= 120 and (len(ts) <= 140): return ("arabic" if chapters == "roman" else "roman"), None
    m = re.match(r"^((?:[A-ZÄÖÜ][A-ZÄÖÜ]+\s?){1,4})\s+([A-ZÄÖÜ][a-zäöüß].*)$", s)   # LABEL Title
    if m and len(m.group(1)) >= 4 and m.group(1).strip().split()[-1] not in ("A", "I"): return "caps", [titlecase(m.group(1)), m.group(2).strip()]
    if caps and len(s) <= 110:
        parts = re.split(r"\s{2,}|\s[-—–]\s", s, maxsplit=1)
        return "caps", [titlecase(x) for x in parts if x.strip()]
    if re.match(r"^(?:ERSTES|ZWEITES|DRITTES|VIERTES|FÜNFTES|SECHSTES)\s+KAPITEL|^(?:Erste[rs]|Zweite[rs]|Dritte[rs]|Vierte[rs])\s+(?:Teil|Kapitel|Abschnitt|Buch)\b|^(?:Part|Book|Chapter|Section)\s+(?:One|Two|Three|Four|[IVX]+|\d+)\b|^(?:Libro|Parte|Capítulo|Livre|Partie|Chapitre)\s+\S+", s, re.I) and len(s) <= 110:
        return "kapitel", None
    if re.match(r"^(?:Vorwort|Vorrede|Einleitung|Einführung|Schluß|Schluss|Nachwort|Anhang|Anmerkungen|Druckfehler|Preface|Foreword|Introduction|Conclusion|Appendix|Notes|Errata|Prólogo|Prefacio|Introducción|Conclusión|Apéndice|Epílogo|Préface|Avant-propos|Zwischenbetrachtung)\b", s, re.I) and len(s) <= 90:
        return "keyword", None
    if re.match(r"^\s*[§$]\s*\d{1,3}\b", s): return "section", [re.sub(r"^\s*[§$]\s*", "§ ", s)] if s.lstrip().startswith("$") else None
    if re.match(r"^" + ROMAN + r"\.\s+\S", s) and len(s) <= 120: return ("roman" if chapters == "roman" else "arabic"), None
    if re.match(r"^\d{1,2}\.\s+[A-ZÄÖÜÁÉÍÓÚÑ„»\"]", s) and len(s) <= 120 and (len(ts) <= 140): return ("arabic" if chapters == "roman" else "roman"), None
    if re.match(r"^[a-z]\.\s+[A-ZÄÖÜÁÉÍÓÚÑ„»\"]", s) and len(s) <= 130: return "letterdot", None
    if re.match(r"^[a-z]\)\s+\S", s) and len(s) <= 130: return "letterparen", None
    if re.match(r"^[αβγδεζηθ]\s?[.)]\s+\S", s) and len(s) <= 130: return "greek", None
    return None, None


_LABEL_RE = re.compile(r"^(?:[ivxlc]{1,6}|\d{1,3}|[a-z]|§\s*\d+)[.)]?\*{0,3}$")

def titlecase(s):
    """ALL-CAPS heading → Title Case. Roman numerals stay upper ("II."), a leading label
    ("2.", "IV.", "b)") does not count as the first word, so the word after it is capitalised."""
    core = MARK_RE.sub("", s)                                  # a lowercase roman page marker ([xi]) is not part of the heading
    if core != core.upper(): return s
    w = s.lower().split(); out = []; first = True; seen_word = False
    for i, x in enumerate(w):
        if MARK_RE.fullmatch(x): out.append(x); continue          # a page marker is not a word
        if _LABEL_RE.match(x) and (not seen_word or re.fullmatch(r"[ivxlc]+\.?\*{0,3}", x)):
            out.append(x.upper() if re.match(r"[ivxlc]", x) else x); first = not seen_word; seen_word = True; continue
        seen_word = True
        core_w = re.sub(r"^[^\w]+", "", x); opens = bool(re.match(r"^[“\"'(\[«]", x))   # “el … → “El …; (la … → (La …
        out.append(x if (not first and not opens and core_w in STOP) else _cap_first(x)); first = False
    return " ".join(out)


def _cap_first(x):
    m = re.match(r"^(\W*)(\w)(.*)$", x, re.S)
    return (m.group(1) + m.group(2).upper() + m.group(3)) if m else x


def runin_lead(o, t, force=False):
    """Run-in title at the start of a paragraph: 'Heraklit. — …' (the skill's convention), or a
    short first sentence when forced. Returns (lead_o, lead_t) or (None, None)."""
    mo = MARGINAL_RE.match(plain(o)); mt = MARGINAL_RE.match(plain(t))
    if mo and mt: return mo.group(1) + ".", mt.group(1) + "."
    if force:
        ro = re.match(r"^(.{3,80}?[.!?][\"“”»)]?)\s+(?=\S)", plain(o)); rt = re.match(r"^(.{3,90}?[.!?][\"“”»)]?)\s+(?=\S)", plain(t))
        if ro and rt: return ro.group(1), rt.group(1)
    return None, None


PN_CUE = re.compile(r'<sup>(\d{1,2})\)</sup>|(?:(?<=[^\s\d>(\[§])|(?<=[«»“”"’] ))(\d)\)(?=[\s.,;:!?)\]—–<]|$)|(?<=[^\s\d(\[§])\((\d{1,3})\)')   # 3rd form: a Markdown cue [^n] glued to its word, "Wort(12)"

def link_page_notes(rows):
    """--page-notes: turn note rows into real footnotes. Each note row is matched to the cue with the same
    number in the body rows since the previous group of notes (else in the next two body rows, else the
    nearest unused cue with that number within six rows either way; failing all, a cue is added at the end
    of the preceding paragraph). The cue becomes <sup class="fr">ID</sup>, the note is attached to its body
    row as notesL / notesR (number stripped); the template sets them at the foot of the page and renumbers
    them per page. Cues left without a note (OCR doubles) are removed from the text."""
    body = [r for r in rows if r["kind"] != "fn"]
    pos = {id(r): i for i, r in enumerate(body)}
    cues = {"left": [], "right": []}           # [body_i, para_j, start, end, num, used]
    for i, r in enumerate(body):
        for side in ("left", "right"):
            for j, h in enumerate(r[side]):
                for m in PN_CUE.finditer(h): cues[side].append([i, j, m.start(), m.end(), int(m.group(1) or m.group(2) or m.group(3)), False])
    notes = []                                  # (nid, side, num, paras, last_body, group_start)
    nid = 0; last_body = -1; group_start = 0; prev_group_lb = -1; in_group = False
    for r in rows:
        if r["kind"] != "fn":
            if in_group: prev_group_lb = last_body; in_group = False
            last_body = pos[id(r)]; continue
        if not in_group: in_group = True; group_start = prev_group_lb + 1
        nid += 1
        for side in ("left", "right"):
            txt = r[side][0] if r[side] else ""
            plain_t = re.sub(r"<[^>]+>", "", txt)
            m = re.match(r"\s*(?:\[[^\]]+\]\s*)*\(?(\d{1,3})\)\s*", plain_t); num = int(m.group(1)) if m else None
            note_html = re.sub(r"^((?:\s*<span class=\"pg\">[^<]*</span>\s*)*)\s*(?:<sup>)?\(?\d{1,3}\)(?:</sup>)?\s*", r"\1", txt, count=1)
            notes.append((nid, side, num, [note_html] + r[side][1:], last_body, group_start, plain_t))
    found = {}
    for pas in (1, 2, 3):
        for nid, side, num, paras, lb, gs, pt in notes:
            if (nid, side) in found: continue
            cand = None
            if pas == 1:
                cand = next((c for c in cues[side] if not c[5] and c[4] == num and gs <= c[0] <= lb), None)
            elif pas == 2:
                cand = next((c for c in cues[side] if not c[5] and c[4] == num and lb < c[0] <= lb + 2), None)
            else:
                near = [c for c in cues[side] if not c[5] and c[4] == num and abs(c[0] - lb) <= 6]
                cand = min(near, key=lambda c: abs(c[0] - lb)) if near else None
            if cand: cand[5] = True; found[(nid, side)] = cand
    repl = {"left": {}, "right": {}}; synth = 0
    for nid, side, num, paras, lb, gs, pt in notes:
        c = found.get((nid, side))
        if c: bi, j = c[0], c[1]; repl[side].setdefault((bi, j), []).append((c[2], c[3], nid))
        else:
            bi = max(lb, 0); j = len(body[bi][side]) - 1; synth += 1
            repl[side].setdefault((bi, j), []).append((None, None, nid))
            if side == "left": print(f"    no cue for note {num}) {pt[:60]!r} → cue added after: …{re.sub(r'<[^>]+>', '', body[bi][side][j])[-50:]!r}")
        body[bi].setdefault("notesL" if side == "left" else "notesR", []).append({"id": nid, "paras": paras})
    stray = 0
    for side in ("left", "right"):
        for c in cues[side]:
            if not c[5]:
                stray += 1   # an unmatched "1)" in body text is an enumeration, not a lost cue: it is left as it stands (Exner 1842)
                if side == "left": print(f"    unmatched cue {c[4]}) left in the text: …{re.sub(r'<[^>]+>', '', body[c[0]]['left'][c[1]][max(0, c[2] - 50):c[2]])!r}")
        for (bi, j), lst in repl[side].items():
            h = body[bi][side][j]
            tail = "".join(f'<sup class="fr">{n}</sup>' for s0, e0, n in lst if s0 is None and n is not None)
            for s0, e0, n in sorted([x for x in lst if x[0] is not None], reverse=True):
                pre = h[:s0].rstrip(" ") if n is not None and h[s0 - 1:s0] == " " and h[s0 - 2:s0 - 1] in "«»“”\"’" else h[:s0]
                h = pre + (f'<sup class="fr">{n}</sup>' if n is not None else "") + h[e0:]
            body[bi][side][j] = h + tail
    print(f"  page notes: {nid} notes set as footnotes; {synth} cue(s) added where the text had none; {stray} unmatched cue(s) left as text")
    return body

def sup_refs(s):
    """word1). → word<sup>1)</sup>. — note references glued to the word (OCR of a raised number)."""
    return re.sub(r'(?<=[A-Za-zäöüßÄÖÜáéíóúñ"”“„»«)\]!?])(\d{1,2})\)', r"<sup>\1)</sup>", s)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Rows
# ══════════════════════════════════════════════════════════════════════════════
def esc(s): return html.escape(s, quote=False)
def ital(h): return h.replace("\ue000", "<i>").replace("\ue001", "</i>")   # --md-italics sentinels

def fmt(s, kind, lead=None, sup=True):
    h = esc(s)
    if lead:
        L = esc(lead)
        if h.startswith(L): h = "<i>" + L + "</i>" + h[len(L):]
    if kind == "fn":
        h = re.sub(r"^((?:\[[^\]]+\]\s*)*)(\d{1,3})\s+(?=[^\d\s])", r"\1<sup>\2</sup> ", h)   # "1 Text" → superscript number
        h = re.sub(r"^((?:\[[^\]]+\]\s*)*)([¹²³⁴⁵⁶⁷⁸⁹⁰]+)\s*", r"\1\2 ", h)
    elif sup: h = sup_refs(h)
    if kind != "fn" and os.environ.get("SBS_SUP_CUES"):   # --sup-cues: Markdown [^n] cues, printed "(n)", as superscripts
        h = re.sub(r"\s?\((\d{1,3}[a-c]?)\)", r"<sup>\1</sup>", h)
    h = re.sub(r"(\[(?:p\.\s*)?(?:[IV]{1,3}\.)?(?:\d{1,4}[a-z]?|[ivxlc]{1,6})(?:[-–]\d{1,4})?\])", r'<span class="pg">\1</span>', h)
    if kind in ("epi", "ver", "orn"): h = h.replace(" / ", " <br>")   # verse written as one paragraph with " / " between lines (space keeps the line splitter from adding a hyphen)
    return ital(h)


def word_boundary(t, p):
    if p <= 0: return 0
    if p >= len(t): return len(t)
    if t[p] == " ": return p
    l, h = p - 1, p + 1
    while l > 0 and t[l] != " ": l -= 1
    while h < len(t) and t[h] != " ": h += 1
    return l if p - l <= h - p else h


def build_rows(pairs, a):
    fmtm = a.marker_format
    levels = dict(KIND_LEVEL); explicit_levels = set()
    for spec in a.level or []:
        k, v = spec.split("="); levels[k.strip()] = int(v); explicit_levels.add(k.strip())
    forced = {}
    for spec in a.kind or []:
        idx, k = spec.split("="); forced[int(idx)] = k.strip()
    runin_idx = set(int(x) for x in (a.runin or "").split(",") if x.strip())
    # page markers from the aligner: page_after → start of the next pair; page_mid → inside the paragraph
    # a heading the source glued to its first paragraph (DOM chapter rows): split at the first sentence end
    fixed = []
    for p in pairs:
        o, t = p.get("orig", "").strip(), p.get("trans", "").strip()
        if p.get("heading") and len(plain(o)) > 160 and "\n" not in o:
            mo = re.match(r"^((?:" + ROMAN + r"\.\s+)?[^.!?]{3,110}[.!?])\s+(\S.*)$", o, re.S); mt = re.match(r"^((?:" + ROMAN + r"\.\s+)?[^.!?]{3,130}[.!?])\s+(\S.*)$", t, re.S)
            if mo and mt:
                fixed.append({**p, "orig": mo.group(1), "trans": mt.group(1), "page_after": None, "page_mid": None})
                fixed.append({**p, "orig": mo.group(2), "trans": mt.group(2), "heading": None, "page_before": None}); continue
        fixed.append(p)
    pairs = explode_multi(fixed, a)
    carry = []
    pb_rows = set()
    rows = []; last_src = None; in_notes = False; prev_kind = "text"; report = []
    for i, p in enumerate(pairs):
        o, t = p["orig"].strip(), p["trans"].strip()
        if p.get("page_mid") is not None and "\n" not in o:
            n = str(p["page_mid"]); off = int(p.get("mid_offset") or 0); mk = fmtm.format(n=n)
            so = word_boundary(o, off); st = word_boundary(t, round(len(t) * off / max(len(o), 1)))
            o = (o[:so].rstrip() + " " + mk + " " + o[so:].lstrip()).strip(); t = (t[:st].rstrip() + " " + mk + " " + t[st:].lstrip()).strip()
        pre = [fmtm.format(n=str(x)) for x in carry]; carry = []
        if p.get("page_before"): pre.append(fmtm.format(n=re.sub(r"^(?:S\.|p\.|Seite|page)\s*", "", str(p["page_before"])).strip("[] ")))
        if pre:
            o = " ".join(pre) + " " + o; t = " ".join(pre) + " " + t
        pa = p.get("page_after")
        if pa: carry = pa if isinstance(pa, list) else [pa]
        if not o and not t: continue
        mk_kind = re.search(r'⟪(\w+)⟫\s*', o)                       # inline display-kind marker (retype.py)
        if mk_kind:
            forced[i] = mk_kind.group(1).replace('ornp', 'orn'); pb_rows.add(i) if mk_kind.group(1) == 'ornp' else None; o = re.sub(r'⟪\w+⟫\s*', '', o); t = re.sub(r'⟪\w+⟫\s*', '', t)
        for mk in MARK_RE.findall(o): last_src = re.sub(r"[\[\]]|p\.\s*", "", mk)
        O = [x for x in o.split("\n") if x.strip()] or [""]; T = [x for x in t.split("\n") if x.strip()] or [""]
        # ── classify ──
        kind = "text"; disp = None; lead = (None, None); level = None; hk = None
        if i in forced:
            k = forced[i]
            if k in ("h1", "h2", "h3"): kind = k; level = int(k[1])
            elif k in ("fn", "text", "epi", "epa", "syn", "orn", "quo", "ver"): kind = k   # ver = verse quoted in the text (body size, indented), epi = epigraph, epa = its attribution, orn = centred ornament (⁂, * * *), quo = block quotation
            elif k == "runin": lead = runin_lead(O[0], T[0], force=True); kind = "text"; hk = "runin"
        else:
            ml = None if getattr(a, "no_md_levels", False) else p.get("md_level")   # `#` depth of a Markdown heading
            if len(O) == 1 or p.get("heading") or ml:
                hk, disp = heading_kind(O[0], T[0], a.toc_chapters)
                if (p.get("heading") or ml) and not hk: hk = "caps"
            if hk:
                level = levels[hk] if hk in explicit_levels else (ml or levels.get(hk, 2)); kind = f"h{min(3, max(1, level))}"
            elif FN_RE.match(O[0]) and (FN_RE.match(T[0]) or len(O[0]) < 400) and not re.match(r"^\d{1,2}\.\s", O[0]):
                kind = "fn"
            elif in_notes and a.notes_appendix:
                kind = "fn"
            else:
                lead = runin_lead(O[0], T[0], force=(i in runin_idx))
                if lead[0]: hk = "runin"
        if hk == "keyword" and re.match(r"^(?:Anhang|Anmerkungen|Appendix|Notes|Apéndice)\b", plain(O[0]), re.I): in_notes = True
        elif kind.startswith("h") and level == 1: in_notes = False
        if disp:   # title-case both columns; keep the original's page marker (plain() stripped it from the display form)
            mk = MARK_RE.findall(O[0]); disp = list(disp)
            if mk and not MARK_RE.search(disp[0]): disp[0] = " ".join(mk) + " " + disp[0]
            O = disp; T = [titlecase(T[0])] if len(disp) == 1 else (split_label(T[0]) or [titlecase(T[0])])
        if kind.startswith("h") and not disp: O = [titlecase(x) for x in O]; T = [titlecase(x) for x in T]   # no-op unless ALL CAPS
        # ── row ──
        toc = None
        if kind.startswith("h") or hk == "runin":
            lvl = level if kind.startswith("h") else levels.get("runin", 2)
            de = lead[0] if hk == "runin" else (": " if kind == "h1" and len(O) > 1 else " ").join(plain(x) for x in O)
            en = lead[1] if hk == "runin" else (": " if kind == "h1" and len(T) > 1 else " ").join(plain(x) for x in T)
            m0 = MARK_RE.findall(O[0])
            de, en = (re.sub(r"\s*\(\d{1,2}\)\s*$", "", x) for x in (de, en))   # a note cue on the heading is not part of the contents label
            toc = {"level": min(3, max(1, lvl)), "de": esc(de.replace("\ue000", "").replace("\ue001", "")), "en": esc(en.replace("\ue000", "").replace("\ue001", "")), "src": (re.sub(r"[\[\]]|p\.\s*", "", m0[-1]) if m0 else last_src)}
            if hk in set(a.toc_skip or []):
                toc = None
        row = {"kind": kind, "left": [fmt(x, kind, lead[0] if j == 0 else None, not a.no_sup_refs) for j, x in enumerate(O)],
               "right": [fmt(x, kind, lead[1] if j == 0 else None, not a.no_sup_refs) for j, x in enumerate(T)],
               "flush": kind == "text" and prev_kind.startswith("h"), "toc": toc}
        if i in pb_rows: row["pb"] = True
        if kind == "fn": row["gap"] = prev_kind != "fn" or bool(re.match(r"^\s*(?:\(\d+\)|\d+\)|\d+\s|\*|[¹²³⁴⁵⁶⁷⁸⁹])", O[0]))
        if kind == "quo":   # block quotation: a run of quo pairs is one row (one block, space above and below)
            if rows and rows[-1]["kind"] == "quo" and not toc:
                rows[-1]["left"] += row["left"]; rows[-1]["right"] += row["right"]; prev_kind = kind
                report.append((i, kind, "", plain(O[0])[:70], plain(T[0])[:50])); continue
            row["gap"] = True; row["gapb"] = True
        rows.append(row); prev_kind = kind
        report.append((i, kind, (hk or "") + (f"+md{p['md_level']}" if p.get("md_level") else ""), plain(O[0])[:70], plain(T[0])[:50]))
    if carry and rows:   # a page beginning after the last paragraph
        rows[-1]["left"][-1] += ' <span class="pg">' + " ".join(fmtm.format(n=str(x)) for x in carry) + "</span>"
    return rows, report


def explode_multi(pairs, a):
    """A pair whose text holds several paragraphs ("\n") becomes one pair per paragraph when both
    sides have the same number; otherwise a leading heading and trailing notes are split off and
    the rest stays one multi-paragraph cell. page_mid is moved into the paragraph it falls in."""
    out = []
    for p in pairs:
        o, t = p.get("orig", "").strip(), p.get("trans", "").strip()
        if "\n" not in o and "\n" not in t: out.append(p); continue
        O = [x.strip() for x in o.split("\n") if x.strip()]; T = [x.strip() for x in t.split("\n") if x.strip()]
        pm, off = p.get("page_mid"), int(p.get("mid_offset") or 0)
        def sub(oo, tt, first, last):
            q = {"orig": oo, "trans": tt}
            if first and p.get("page_before"): q["page_before"] = p["page_before"]
            if last and p.get("page_after"): q["page_after"] = p["page_after"]
            return q
        if len(O) == len(T):
            pos = 0
            for j, (oo, tt) in enumerate(zip(O, T)):
                q = sub(oo, tt, j == 0, j == len(O) - 1)
                if pm is not None and pos <= off <= pos + len(oo): q["page_mid"] = pm; q["mid_offset"] = off - pos; pm = None
                pos += len(oo) + 1; out.append(q)
            continue
        hk, _ = heading_kind(O[0], T[0] if len(T[0]) < 200 else "", a.toc_chapters)
        if hk:
            th = T[0]
            if len(T) < len(O) and len(th) >= 200:
                m = re.match(r"^\s*(?:\[[^\]]+\]\s*)?(?:[IVX]+\.|[a-z]\s?[.)]|\d{1,2}\.|§\s*\d+\.)\s*", th); k = th.find(". ", m.end() if m else 0)
                if k > 0: th, rest = th[:k + 1], th[k + 2:]; T = [th] + [rest] + T[1:]
            out.append(sub(O[0], T[0], True, False)); O, T = O[1:], T[1:]
            if not O: continue
        fo = next((j for j in range(len(O)) if FN_RE.match(O[j]) and not re.match(r"^\d{1,2}\.\s", O[j])), None)
        ft = next((j for j in range(len(T)) if FN_RE.match(T[j])), None)
        if fo is not None and fo > 0:
            ft = len(T) if ft is None else ft
            out.append(sub("\n".join(O[:fo]), "\n".join(T[:ft]), False, False)); out.append(sub("\n".join(O[fo:]), "\n".join(T[ft:]), False, True))
        else:
            out.append(sub("\n".join(O), "\n".join(T), False, True))
    return out


def split_label(t):
    m = re.match(r"^((?:[A-Z][A-Z]+\s?){1,4})\s+([A-Z][a-z].*)$", plain(t))
    return [titlecase(m.group(1)), m.group(2).strip()] if m else None


# ══════════════════════════════════════════════════════════════════════════════
# 4. Render
# ══════════════════════════════════════════════════════════════════════════════
def font_css():
    css = []
    for (style, weight), fn in FONT["files"].items():
        b = base64.b64encode((ASSETS / "fonts" / fn).read_bytes()).decode()
        css.append(f"@font-face{{font-family:'{FONT['family']}';font-style:{style};font-weight:{weight};src:url(data:font/ttf;base64,{b}) format('truetype');}}")
    return "\n".join(css)


def find_chrome(explicit):
    cands = [explicit] if explicit else []
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
              os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        w = shutil.which(name)
        if w: cands.append(w)
    for c in cands:
        if c and Path(c).exists(): return c
    sys.exit("Google Chrome / Chromium not found. Install Chrome or pass --chrome /path/to/binary.")


def render(chrome, html_path, pdf_path, workdir, timeout=300):
    profile = workdir / "chrome-profile"; shutil.rmtree(profile, ignore_errors=True)
    if pdf_path.exists(): pdf_path.unlink()
    log = workdir / "chrome.log"
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}", "--no-pdf-header-footer",
           "--virtual-time-budget=90000", "--enable-logging=stderr", "--v=0", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
    with open(log, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=lf)
        t0 = time.time(); last = -1; stable = 0
        while time.time() - t0 < timeout:
            if proc.poll() is not None and pdf_path.exists(): break
            if pdf_path.exists():
                size = pdf_path.stat().st_size; stable = stable + 1 if size == last and size > 0 else 0; last = size
                if stable >= 2: break
            time.sleep(1)
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(5)
            except subprocess.TimeoutExpired: proc.kill()
    stats = {}; warns = []
    for line in log.read_text(errors="replace").splitlines():
        m = re.search(r'STATS (\{.*\})', line)
        if m:
            try: stats = json.loads(m.group(1).replace('\\"', '"'))
            except Exception: pass
        if "CONSOLE" in line and "WARN" in line: warns.append(re.sub(r".*CONSOLE[^\]]*\]\s*", "", line)[:160])
        if "Uncaught" in line or "SyntaxError" in line: warns.append(line[:200])
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0: sys.exit(f"Chrome produced no PDF. See {log}")
    return stats, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original", help="orig.txt / .md / .epub, or a side-by-side .html, or a pairs .json")
    ap.add_argument("translation", nargs="?", help="trans.txt / .md (omit for .html / .json input)")
    ap.add_argument("-o", "--output", help="output PDF (default: ~/Desktop/<work slug>.pdf)")
    ap.add_argument("--author", default="", help="title block line 1")
    ap.add_argument("--work", default="", help="title block line 2 (HTML ok); default: the HTML <title> or --title")
    ap.add_argument("--title", default="", help="fallback for --work and the PDF title")
    ap.add_argument("--running-head", default="", help="pages 2+ header (HTML ok); default 'Surname, <i>Work</i>'")
    ap.add_argument("--credit", default="", help="line under the title, e.g. 'Translation: E. S., 2026'")
    ap.add_argument("--edition", default="", help="text basis for the auto-composed editorial footnote, e.g. 'the first edition of 1846' or 'Gesamtausgabe vol. 28'")
    ap.add_argument("--footnote", action="append", default=[], help="editorial footnote for page 1 (HTML ok); replaces the auto-composed one; repeatable")
    ap.add_argument("--lang", nargs=2, metavar=("LEFT", "RIGHT"), help="BCP-47 codes, e.g. de en — set both (hyphenation, TOC labels, footnote wording)")
    ap.add_argument("--toc-chapters", choices=["roman", "arabic"], default="roman", help="which numbered headings are top-level (as in side_by_side_html.py)")
    ap.add_argument("--level", action="append", metavar="KIND=N", help="TOC/heading level for a heading kind: caps kapitel keyword roman section arabic letterdot letterparen greek runin (defaults: caps/kapitel/keyword/roman=1, section/arabic/letterdot/runin=2, letterparen/greek=3)")
    ap.add_argument("--toc-skip", action="append", metavar="KIND", help="heading kind to exclude from the TOC (still styled as a heading in the body); repeatable: --toc-skip section --toc-skip letterparen")
    ap.add_argument("--kind", action="append", metavar="IDX=KIND", help="force a pair: IDX=h1|h2|h3|fn|text|runin|epi|epa|syn|orn|quo|ver (verse in the text at body size, indented; epigraph, its attribution, synopsis/outline line with hanging indent, centred section-break ornament such as ⁂, indented block quotation in note type)")
    ap.add_argument("--runin", default="", help="comma-separated pair indexes whose first sentence is a run-in section title (italic + TOC)")
    ap.add_argument("--notes-appendix", action="store_true", default=True, help="paragraphs after an Anhang/Appendix/Notes heading are notes (smaller type) [default]")
    ap.add_argument("--no-notes-appendix", dest="notes_appendix", action="store_false")
    ap.add_argument("--no-sup-refs", action="store_true", help="do not raise note references glued to words (word1) → word¹⁾)")
    ap.add_argument("--marker-format", default="[{n}]", help="how page numbers from the aligner appear (default '[{n}]')")
    ap.add_argument("--left-ratio", type=float, default=0.5); ap.add_argument("--paper", choices=list(PAPER), default="letter")
    ap.add_argument("--chapter-breaks", action="store_true", help="landscape layout: every level-1 heading (chapter, preface, appendix) opens a new page, as --facing always does")
    ap.add_argument("--page-notes", action="store_true", help="set the author's notes as real footnotes at the foot of each page (each column its own), cued by superscript numbers renumbered per page, instead of in the flow after their paragraph")
    ap.add_argument("--sup-cues", action="store_true", help="set note cues \"(n)\" in the text as superscript numbers (the note paragraphs keep \"(n)\")")
    ap.add_argument("--md-italics", action="store_true", help="Markdown inputs: keep *single-star* emphasis as italics instead of stripping it")
    ap.add_argument("--break-bars", action="store_true", help="with --margin-folios: leave a thin red bar in the text where each source page begins, and set the margin numbers in red (Trendelenburg style)")
    ap.add_argument("--note-labels", default="", metavar="JSON", help="with --page-notes: a JSON list of the printed note numbers in note order; marks keep them instead of renumbering per page")
    ap.add_argument("--note-marks", default="{n}", metavar="FMT", help="with --page-notes: how the per-page note marks look: '{n}' (1, 2 …, default), '{n})' (1), 2) …), '*' (*), **) … as in many 19th-c. books)")
    ap.add_argument("--margin-folios", action="store_true", help="landscape layout: lift the [n] page markers out of the text into the outer margins (original left, translation right), as --facing always does")
    ap.add_argument("--facing", action="store_true", help="book layout: portrait pages, original on each verso (even) page and translation on the facing recto, paragraph starts aligned across the spread, page numbers on every page")
    ap.add_argument("--font-size", type=float, metavar="PX", help="body size in CSS px (default 15.5; 16.5 with --facing)"); ap.add_argument("--line-height", type=int, metavar="PX", help="body leading in px (default 18; 20 with --facing)")
    ap.add_argument("--trim", default="6x9", metavar="WxH", help="(with --facing) trim size in inches, e.g. 6x9, 5.5x8.5, 5x8")
    ap.add_argument("--break-level", type=int, default=1, choices=[1,2], metavar="N", help="(with --facing) headings of level <= N open a fresh page (default 1: chapters/part titles only; 2: sections too)")
    ap.add_argument("--margins", default="0.875,0.625,0.9,0.75", metavar="IN,OUT,TOP,BOTTOM", help="(with --facing) margins in inches: inside (gutter), outside, top (to the text, the running head sits above), bottom")
    ap.add_argument("--detect-paragraphs", action="store_true")
    ap.add_argument("--front-matter", choices=["auto", "keep"], default="auto", help="auto (default): of several heading rows before the first body paragraph (half-title, title page, title again) only the last enters the contents; keep: all of them")
    ap.add_argument("--toc-skip-idx", default="", metavar="IDX,IDX", help="pair indexes to leave out of the contents (still set as headings)")
    ap.add_argument("--no-md-levels", action="store_true", help="Markdown original: ignore the `#` depth of headings (use the kind defaults / --level instead)")
    ap.add_argument("--no-propagate-markers", action="store_true", help="do not copy the original's inline [n] page markers into a translation that carries none")
    ap.add_argument("--inspect", action="store_true", help="print the classification (headings, notes, run-in titles) with pair indexes and exit")
    ap.add_argument("--list", action="store_true", help="print every pair index with the first words of both sides (the indexes --kind/--runin refer to) and exit")
    ap.add_argument("--dump-rows", metavar="JSON", help="write the rows fed to the engine (for hand corrections) and exit")
    ap.add_argument("--rows", metavar="JSON", help="render from a rows JSON written by --dump-rows (after editing)")
    ap.add_argument("--chrome"); ap.add_argument("--no-bookmarks", action="store_true", help="do not add PDF bookmarks from the contents (needs pypdf)"); ap.add_argument("--keep-html", action="store_true"); ap.add_argument("--preview", type=int, default=0, metavar="N")
    a = ap.parse_args()
    if a.md_italics: os.environ["SBS_MD_ITALICS"] = "1"
    if a.sup_cues: os.environ["SBS_SUP_CUES"] = "1"

    src = Path(a.original).expanduser().resolve()
    if not src.exists(): sys.exit(f"Input not found: {src}")
    meta_title, labels, html_lang = "", [], None
    print(f"→ {src.name}" + (f" + {a.translation}" if a.translation else ""))
    if a.rows:
        rows = json.load(open(a.rows, encoding="utf-8")); report = []; pairs = []
    else:
        if src.suffix.lower() == ".html":
            pairs = pairs_from_html(src); meta_title, labels, html_lang = html_meta(src)
        elif src.suffix.lower() == ".json":
            pairs = json.load(open(src, encoding="utf-8")); pairs = pairs.get("pairs", pairs) if isinstance(pairs, dict) else pairs
        else:
            if not a.translation: sys.exit("Give the translation file as the second argument.")
            pairs = pairs_from_texts(src, Path(a.translation).expanduser().resolve(), a.detect_paragraphs, propagate=not a.no_propagate_markers)
        print(f"  {len(pairs)} pairs")
        rows, report = build_rows(pairs, a)
    if not a.rows:
        skip = {int(x) for x in a.toc_skip_idx.split(",") if x.strip()}
        lead = 0
        while lead < len(rows) and rows[lead]["kind"].startswith("h"): lead += 1
        if a.front_matter == "auto" and lead >= 2: skip.update(report[k][0] for k in range(lead - 1))
        for k, rp in enumerate(report):
            if rp[0] in skip and rows[k].get("toc"): rows[k]["toc"] = None
        if skip & {rp[0] for rp in report}: print(f"  contents: skipped pair(s) {sorted(skip & {rp[0] for rp in report})}" + (" (front matter)" if a.front_matter == "auto" and lead >= 2 else ""))
    kinds = {}
    for r in rows: kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("  rows:", ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())), f"| TOC entries: {sum(1 for r in rows if r.get('toc'))}")
    if a.list:
        for i, kind, hk, o, t in report: print(f"  {i:4d}  {kind:4s} {o[:60]!r} | {t[:40]!r}")
        return
    if a.inspect:
        print("\n  idx  kind  pattern      original | translation")
        for i, kind, hk, o, t in report:
            if kind != "text" or hk: print(f"  {i:4d}  {kind:4s}  {hk or '':12s} {o!r} | {t!r}")
        print("\n  Correct with --level KIND=N, --kind IDX=KIND, --runin IDX,IDX; then run again without --inspect.")
        return
    if a.dump_rows:
        Path(a.dump_rows).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"); print(f"  wrote {a.dump_rows}"); return

    if getattr(a, "page_notes", False): rows = link_page_notes(rows)
    lang_l, lang_r = a.lang if a.lang else ((html_lang or "en"), "en")
    if not a.lang: print(f"  [!] --lang not given; using {lang_l} {lang_r} (hyphenation and labels depend on it)")
    work = a.work or a.title or meta_title or src.stem.replace("_", " ").replace("-", " ")
    surname = a.author.split()[-1] if a.author else ""
    running = a.running_head or (f"{surname}, <i>{re.sub('<[^>]+>', '', work)}</i>" if surname else f"<i>{re.sub('<[^>]+>', '', work)}</i>")
    footnotes = list(a.footnote)
    if not footnotes and a.edition:
        n_fn = sum(1 for r in rows if r["kind"] == "fn"); has_marks = any('class="pg"' in x for r in rows for x in r["left"])
        s = f"{LANG_NAME.get(lang_l, 'Original')} text follows {a.edition}."
        if has_marks and getattr(a, "break_bars", False): s += " The numbers in the outer margins give the page numbers of that edition; a thin red bar in the text marks the exact point where each page begins."
        elif has_marks and getattr(a, "margin_folios", False): s += " The numbers in the outer margins give the page numbers of that edition."
        elif has_marks: s += " Numbers in square brackets indicate page numbers in that edition."
        if n_fn: s += " The author’s notes are set as footnotes at the foot of each page." if getattr(a, "page_notes", False) else " The author’s notes are set in smaller type where they occur in the text."
        s += " Page numbers in the right-hand column of the table of contents refer to this edition."
        footnotes = [s]
    if a.facing: FONT["size"], FONT["lh"] = 16.5, 20
    if a.font_size: FONT["size"] = a.font_size
    if a.line_height: FONT["lh"] = a.line_height
    w, h = PAPER[a.paper]; gutter = 36; margin_x = 134; lh = FONT["lh"]; k = lh / 16
    facing = {}
    if a.facing:
        tw, th = (float(x) for x in a.trim.lower().split("x")); m_in, m_out, m_top, m_bot = (float(x) for x in a.margins.split(","))
        w, h = round(tw * 96), round(th * 96)
        facing = {"facing": True, "break_level": a.break_level, "m_in": round(m_in * 96), "m_out": round(m_out * 96), "text_top": round(m_top * 96), "margin_bottom": round(m_bot * 96), "title_top": round(h * 0.28)}
        margin_x = facing["m_out"]; gutter = 0
    col_total = (w - 2 * margin_x) - gutter; wl = round(col_total * a.left_ratio); wr = col_total - wl
    if a.facing: wl = wr = w - facing["m_in"] - facing["m_out"]
    config = {"page_w": w, "page_h": h, "margin_x": margin_x, "text_top": 100, "margin_bottom": 108, "gutter": gutter,
              "left_ratio": a.left_ratio, "line_height": lh, "fn_line_height": 15,
              "font_loads": [f"{st} {wt} {FONT['size']}px '{FONT['family']}'" for (st, wt) in FONT["files"]],
              "title_top": 100, "title_gap": 30, "author": a.author, "work_line": work, "credit": a.credit, "running_head": running,
              "footnotes": footnotes, "toc_title_left": TOC_TITLE.get(lang_l, "Contents"), "toc_sub_left": "",
              "toc_title_right": TOC_TITLE.get(lang_r, "Contents"), "toc_sub_right": "Page" if lang_r == "en" else "",
              "lang_left": lang_l, "lang_right": lang_r,
              "doc_title": re.sub("<[^>]+>", "", f"{a.author} — {work}").strip(" —")}
    config.update(facing)
    config["margin_folios"] = bool(getattr(a, "margin_folios", False))
    config["break_bars"] = bool(getattr(a, "break_bars", False)); config["note_marks"] = a.note_marks; config["note_labels"] = json.load(open(a.note_labels)) if a.note_labels else None
    config["page_notes"] = bool(getattr(a, "page_notes", False))
    config["chapter_breaks"] = bool(getattr(a, "chapter_breaks", False)); config.setdefault("break_level", a.break_level)
    if any(r.get("toc") and r["toc"].get("src") for r in rows):
        ed = re.sub(r"^(?:the\s+)?(?:first\s+)?", "", a.edition).strip() if a.edition else ""
        config["toc_sub_left"] = ("Seite" if lang_l == "de" else "Página" if lang_l in ("es", "pt") else "Page") + (f" ({ed})" if ed and len(ed) < 30 else "")
    tpl = (ASSETS / "pdf_template.html").read_text(encoding="utf-8")
    sizes = {"FONT_CSS": font_css(), "FONT_FAMILY": FONT["family"], "FONT_WEIGHT": FONT["weight"], "FS": FONT["size"], "LH": lh,
             "FS_AUTHOR": round(16 * k, 2), "LH_AUTHOR": round(20 * k), "FS_WORK": round(19.2 * k, 2), "LH_WORK": round(24 * k),
             "FS_SUP": round(9 * k, 2), "FS_FN": round(10.6 * k, 2), "LH_FN": round(13 * k), "FS_FN2": 12.6, "LH_FN2": 15,
             "FS_TOC": 13.5, "LH_TOC": 16, "COL_L_W": wl, "COL_R_W": wr, "GUTTER": gutter, "PAGE_W": w, "PAGE_H": h,
             "TITLE": html.escape(config["doc_title"] or "parallel edition"),
             "CONFIG_JSON": json.dumps(config, ensure_ascii=False), "ROWS_JSON": json.dumps(rows, ensure_ascii=False)}
    for key, val in sizes.items(): tpl = tpl.replace("{{" + key + "}}", str(val))
    slug = re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", re.sub("<[^>]+>", "", work).lower())).strip("-") or "parallel-edition"
    out = Path(a.output).expanduser().resolve() if a.output else (Path.home() / "Desktop" / f"{slug}.pdf")
    workdir = out.parent / f".{out.stem}_build"; workdir.mkdir(parents=True, exist_ok=True)
    html_path = workdir / "print.html"; html_path.write_text(tpl, encoding="utf-8")
    print("  rendering with Chrome …")
    stats, warns = render(find_chrome(a.chrome), html_path, out, workdir)
    for wmsg in warns: print("  ! " + wmsg)
    npages = None
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout
        m = re.search(r"Pages:\s+(\d+)", info); npages = int(m.group(1)) if m else None
    print(f"  layout: {stats.get('pages', '?')} pages ({stats.get('front', '?')} front matter + {stats.get('body', '?')} text{' in facing pairs' if a.facing else ''}), {stats.get('toc_entries', '?')} contents entries"
          + (f"; PDF has {npages} pages" if npages else ""))
    if stats.get("pages") and npages and stats["pages"] != npages: print("  ! page count mismatch between layout and PDF")
    if stats.get("toc") and not a.no_bookmarks:
        try:
            from pypdf import PdfReader, PdfWriter
            wr = PdfWriter(clone_from=PdfReader(str(out)))
            wr.add_outline_item(TOC_TITLE.get(a.lang[1], "Contents") if a.lang else "Contents", 0)
            parents = {}
            for e in stats["toc"]:
                lvl, pg = int(e.get("l", 1)), int(e.get("p", 1)) - 1
                if not 0 <= pg < len(wr.pages): continue
                parents[lvl] = wr.add_outline_item(e.get("t") or "—", pg, parent=parents.get(lvl - 1))
                for d in [l for l in parents if l > lvl]: del parents[d]
            wr.page_mode = "/UseOutlines"
            if a.author or a.work: wr.add_metadata({"/Title": re.sub("<[^>]+>", "", a.title or a.work or ""), "/Author": a.author or ""})
            with open(out, "wb") as fh: wr.write(fh)
            print(f"  bookmarks: {len(stats['toc'])} contents entries (pypdf)")
        except ImportError:
            print("  (no pypdf: PDF bookmarks skipped — pip install pypdf)")
    if a.preview and shutil.which("pdftoppm"):
        prev = out.parent / f"{out.stem}_preview"; prev.mkdir(exist_ok=True)
        subprocess.run(["pdftoppm", "-r", "80", "-png", "-f", "1", "-l", str(a.preview), str(out), str(prev / "page")])
        print(f"  previews: {prev}/page-*.png")
    if a.keep_html: shutil.copy(html_path, out.with_suffix(".print.html")); print(f"  kept {out.with_suffix('.print.html').name}")
    shutil.rmtree(workdir, ignore_errors=True)
    print(f"✓ {out}")


if __name__ == "__main__":
    main()
