#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_clean.py — one pass of OCR-debris repair on a Markdown source, written to a refined copy.

    python3 md_clean.py BOOK.ocr.md                 # → BOOK.ocr.refined.md + report
    python3 md_clean.py TRANS.md --side trans       # LLM translation: chatter/placeholders only
    python3 md_clean.py BOOK.ocr.md -o out.md | --in-place

Mechanical repairs (counted in the report; the original file is never touched unless --in-place):
  pipes from line-break OCR (`ame- | ricana` → `americana`, `su | sentido` → `su sentido`), hyphen
  + stray digit (`pues- 7 ta` → `puesta`), Markdown escapes (`\\-`), stray punctuation opening a
  paragraph (`. El sistema`, `( Como`, `” Así`), a space before `.,;:`, doubled spaces, paragraphs
  of fewer than three letters (`# o`), a paragraph ending in a hyphen or mid-sentence followed by a
  paragraph starting lowercase (page-break split: joined, a `[n]` marker kept before the word).

Flagged, not changed (each with its book page, so the scan can be checked with scan_page.py):
  headings that look like OCR debris, short lowercase fragments (a paragraph tail the OCR cut off),
  words with a period, bracket or digit inside (`sim.bolista`, `esencia]`), a heading level mix
  (`#` and `##` both present — check two scan pages: old books often set all sections alike).
Everything else — misread letters, missing accents — is left as found; fix_orig.py handles it."""
from __future__ import annotations
import argparse, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

RULES_ORIG = [
    ("hyphen + pipe join",        r"(\w)-\s*\|\s*(\w)",                      r"\1\2"),
    ("pipe",                      r"[ \t]*\|[ \t]*",                          " "),
    ("hyphen + stray digit",      r"(\w)- [0-9]{1,2} (\w)",                   r"\1\2"),
    ("hyphen + stray letter",     r"(\w)- [a-zA-ZÑñ] (\w)",                   r"\1\2"),
    ("markdown escape",           r"\\([-*_#\[\]().!])",                       r"\1"),
    ("stray opening punctuation", r"(?m)^(?:#+\s+)?[.,;:'’”\"»)\]_¡¿]+ +(?=[A-ZÁÉÍÓÚÑÜ¿¡“\"(«])", lambda m: (m.group(0).split()[0] + " ") if m.group(0).startswith("#") else ""),
    ("space before punctuation",  r"(?<=\w) ([,.;:])(?=\s|$)",                r"\1"),
    ("doubled spaces",            r"[ \t]{2,}",                               " "),
]
RULES_TRANS = [("markdown escape", r"\\([-*_#\[\]().!])", r"\1"), ("doubled spaces", r"[ \t]{2,}", " ")]
PAGE_ALONE = re.compile(r"^\s*(?:\*\*)?\[(\d{1,4})\](?:\*\*)?\s*$")


def page_of(paras, i):
    """Book page a paragraph is on: the last [n] seen before or inside it."""
    pg = None
    for k in range(i + 1):
        for m in re.finditer(r"\[(\d{1,4})\]", paras[k]): pg = int(m.group(1))
    return pg


FRENCH = re.compile(r"\b(?:les|des|une|est|que|qui|dans|pour|pas|sont|nous|cette|être)\b", re.I)


def looks_french(text: str) -> bool:
    words = max(len(text.split()), 1)
    return len(FRENCH.findall(text[:60000])) / min(words, 10000) > 0.06


def clean(text: str, side: str = "orig", lang: str | None = None):
    text = text.replace("\r\n", "\n"); counts = {}
    french = (lang or "").lower().startswith("fr") or (lang is None and looks_french(text))
    rules = RULES_ORIG if side == "orig" else RULES_TRANS
    if french: rules = [r for r in rules if r[0] != "space before punctuation"]; counts["French typography kept (space before ; : ? !)"] = 1
    for name, pat, rep in rules:
        text, n = re.subn(pat, rep, text)
        if n: counts[name] = counts.get(name, 0) + n
    paras = [b for b in re.split(r"\n\s*\n", text)]
    out = []; flagged = {"junk_heading": [], "fragment": [], "inner_punct": []}; dropped = 0
    for b in paras:
        s = b.strip()
        if not s: continue
        if s.startswith("<!--"): out.append(s); continue
        if side == "orig" and not PAGE_ALONE.match(s) and sum(c.isalpha() for c in s) < 3 and not re.search(r"\d", s) and not re.fullmatch(r"#*\s*[IVXLC]{1,6}\.?|\*\s*\*\s*\*", s):   # keep "IV." headings and * * * breaks
            dropped += 1; continue                                        # `# o`, `Ñ`, `.`
        out.append(s)
    if dropped: counts["paragraph with < 3 letters dropped"] = dropped
    # page-break splits: ends with a hyphen (or mid-sentence) + next starts lowercase → join
    if side == "orig":
        joined = []; i = 0; nj = 0
        while i < len(out):
            cur = out[i]
            while i + 1 < len(out):
                nxt = out[i + 1]; mk = re.match(r"^(\[\d{1,4}\])\s+(.*)$", nxt, re.S)
                body = mk.group(2) if mk else nxt
                if PAGE_ALONE.match(nxt) or cur.startswith("#") or nxt.startswith("#") or not body[:1].islower(): break
                if re.search(r"\w-$", cur):
                    w = re.search(r"(\w+)-$", cur).group(1); cur = cur[: -len(w) - 1] + ((mk.group(1) + " ") if mk else "") + w + body
                elif not re.search(r"[.!?…:;\"”»’')\]]$", cur):
                    cur = cur + " " + nxt
                else: break
                nj += 1; i += 1
            joined.append(cur); i += 1
        out = joined
        if nj: counts["page-break split joined"] = nj
    for i, s in enumerate(out):
        core = re.sub(r"^#+\s+", "", s)
        if s.startswith("#"):
            letters = sum(c.isalpha() for c in core)
            body = re.sub(r"^(?:[IVXLC]+\.|\d{1,2}[.°]|[a-z]\))\s*[—–-]?\s*", "", core)   # numbering does not count as lowercase
            if letters < 3 or (body == body.lower() and not re.search(r"\d", core)) or not re.search(r"[aeiouáéíóúAEIOUÁÉÍÓÚ]", core): flagged["junk_heading"].append((i, page_of(out, i), core[:60]))
        elif len(core) < 60 and core[:1].islower() and not PAGE_ALONE.match(core): flagged["fragment"].append((i, page_of(out, i), core[:60]))
        for m in re.finditer(r"\b\w{2,}[.\]]\w{3,}\b|\b[A-Za-zÁÉÍÓÚáéíóúñÑ]+\d+[A-Za-záéíóúñ]+\b", core):
            flagged["inner_punct"].append((i, page_of(out, i), m.group(0)))
    levels = sorted({len(re.match(r"^#+", s).group(0)) for s in out if s.startswith("#")})
    if "heading levels from the document" in text: levels = levels[:1]      # styles, not a type-size guess: no warning
    return "\n\n".join(out) + "\n", {"counts": counts, "flagged": flagged, "heading_levels": levels, "paragraphs": sum(1 for s in out if not PAGE_ALONE.match(s))}


def report(rep, name):
    L = [f"  md_clean {name}: {rep['paragraphs']} paragraphs"]
    for k, v in rep["counts"].items(): L.append(f"    {v:4d}  {k}")
    lab = {"junk_heading": "heading that looks like OCR debris — delete it, or it is a paragraph tail: check the scan",
           "fragment": "short lowercase fragment — a cut-off paragraph tail: check the scan page",
           "inner_punct": "word with punctuation/digit inside — OCR slip, fix_orig.py"}
    for k, items in rep["flagged"].items():
        if not items: continue
        L.append(f"    [!] {len(items)} {lab[k]}:")
        for i, pg, t in items[:12]: L.append(f"          [{i}] p.{pg}: {t!r}")
        if len(items) > 12: L.append(f"          … {len(items) - 12} more (see the JSON report)")
    if len(rep["heading_levels"]) > 1: L.append(f"    [!] heading levels {rep['heading_levels']} both occur — OCR font-size guess; check two scan pages before trusting the hierarchy (fix with fix_orig.py --regex '^## ' '# ')")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file"); ap.add_argument("--side", choices=["orig", "trans"], default="orig")
    ap.add_argument("-o", "--output"); ap.add_argument("--in-place", action="store_true"); ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--lang", help="language of the file (fr keeps the space before ; : ? !); detected from the text when omitted")
    a = ap.parse_args(); src = pathlib.Path(a.file).expanduser()
    text, rep = clean(src.read_text(encoding="utf-8"), a.side, a.lang)
    out = src if a.in_place else pathlib.Path(a.output).expanduser() if a.output else src.with_name(re.sub(r"\.md$", "", src.name) + ".refined.md")
    out.write_text(text, encoding="utf-8"); print(report(rep, src.name)); print(f"  → {out}")
    if a.json: pathlib.Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__": main()
