#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rtf_to_md.py — a Word/RTF transcription (Classiques des sciences sociales, Gallica exports…) → Markdown.

    python3 rtf_to_md.py BOOK.rtf [-o BOOK.md] [--list-headings]

Keeps what the parallel-edition tools need and nothing else: paragraphs (blank-line separated), headings
from the RTF heading styles (heading 1…9 → #…, "Titre 1 bis" → #), footnotes as `[^n]` cues with the note
text right after the paragraph (`[^n]: …`), page numbers written as [n] in the text left as they are,
hyperlink text without the link, no images, no index entries, no fields. Encoding: \\'xx bytes decoded in the
file's code page (\\ansicpg), \\uN Unicode escapes honoured. Prints a summary; --list-headings prints every
heading with its level so the hierarchy can be checked before building."""
from __future__ import annotations
import argparse, pathlib, re

SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "headerl", "headerr", "footerl", "footerr", "headerf", "footerf",
        "xe", "tc", "fldinst", "datafield", "themedata", "colorschememapping", "latentstyles", "rsidtbl", "generator", "pgdsctbl", "listtable",
        "listoverridetable", "revtbl", "bkmkstart", "bkmkend", "object", "shppict", "nonshppict", "pntext", "pn", "template", "docvar", "userprops",
        "mmathPr", "wgrffmtfilter", "ftnsep", "ftnsepc", "aftnsep", "aftnsepc", "annotation", "atnid", "atnauthor", "pgp", "pgptbl", "protend", "protstart"}
CODEPAGES = {10000: "mac_roman", 1252: "cp1252", 1250: "cp1250", 1251: "cp1251", 28591: "latin-1", 65001: "utf-8"}


def convert(data: bytes):
    text = data.decode("latin-1")
    m = re.search(r"\\ansicpg(\d+)", text[:2000]); cp = CODEPAGES.get(int(m.group(1)) if m else 1252, "cp1252")
    paras = []            # (style, text)
    notes = []            # note texts
    stack = []            # saved (skip, in_note, uc)
    skip = False; in_note = False; uc = 1; style = 0
    buf = []; nbuf = []; skip_units = 0
    i = 0; n = len(text)

    def out(ch):
        nonlocal skip_units
        if skip_units > 0: skip_units -= 1; return
        if skip: return
        (nbuf if in_note else buf).append(ch)

    def end_para():
        t = re.sub(r"[ \t\u00a0]+", " ", "".join(buf)).strip()
        if t: paras.append((style, t))
        buf.clear()

    while i < n:
        c = text[i]
        if c == "{":
            stack.append((skip, in_note, uc)); i += 1
            # destination?
            m = re.match(r"\\\*\\([a-zA-Z]+)|\\([a-zA-Z]+)", text[i:i + 40])
            if m:
                word = m.group(1) or m.group(2)
                if m.group(1) is not None or word in SKIP:
                    if word == "footnote":
                        in_note = True; nbuf = []
                    elif word in SKIP or m.group(1) is not None:
                        skip = True
                if word == "footnote" and m.group(1) is None:
                    in_note = True; nbuf = []
            continue
        if c == "}":
            if in_note and not (stack and stack[-1][1]):
                # closing the footnote group
                t = re.sub(r"\s+", " ", "".join(nbuf)).strip(); t = re.sub(r"^\d{1,3}\s*", "", t)
                notes.append(t); buf.append(f"[^{len(notes)}]")
            if stack: skip, in_note, uc = stack.pop()
            i += 1; continue
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?", text[i:i + 32])
            if m:
                word, param = m.group(1), m.group(2); i += m.end()
                if word == "par" or word == "page" or word == "sect":
                    if in_note: nbuf.append(" ")
                    elif not skip: end_para()
                elif word == "pard":
                    if not in_note: style = 0
                elif word == "s" and param is not None and not in_note and not skip: style = int(param)
                elif word == "line": out(" ")
                elif word == "tab": out(" ")
                elif word == "cell" or word == "row": out(" ")
                elif word == "uc" and param is not None: uc = int(param)
                elif word == "u" and param is not None:
                    v = int(param); v = v + 65536 if v < 0 else v
                    if not skip: out(chr(v)); skip_units = uc if not skip else 0
                    else: skip_units = 0
                elif word == "emdash": out("—")
                elif word == "endash": out("–")
                elif word == "lquote": out("‘")
                elif word == "rquote": out("’")
                elif word == "ldblquote": out("“")
                elif word == "rdblquote": out("”")
                elif word == "bullet": out("•")
                elif word == "chftn": pass
                continue
            m = re.match(r"\\'([0-9a-fA-F]{2})", text[i:i + 4])
            if m:
                i += 4
                if skip_units > 0: skip_units -= 1; continue
                out(bytes([int(m.group(1), 16)]).decode(cp, "replace")); continue
            sym = text[i + 1] if i + 1 < n else ""
            i += 2
            if sym == "~": out("\u00a0")
            elif sym == "-": pass
            elif sym == "_": out("-")
            elif sym in "{}\\": out(sym)
            elif sym == "*": pass
            continue
        if c in "\r\n": i += 1; continue
        out(c); i += 1
    end_para()
    return paras, notes


def to_markdown(paras, notes):
    out = ["<!-- rtf_to_md: heading levels from the document's own styles -->"]
    for style, t in paras:
        if re.fullmatch(r"\[\d{1,4}\]", t): out.append(t); continue
        level = style if 1 <= style <= 9 else (1 if style == 53 else 0)
        line = ("#" * min(level, 6) + " " + t) if level else t
        out.append(line)
        for m in re.finditer(r"\[\^(\d+)\]", t):
            k = int(m.group(1))
            if k - 1 < len(notes): out.append(f"[^{k}]: {notes[k - 1]}")
    return "\n\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rtf"); ap.add_argument("-o", "--output"); ap.add_argument("--list-headings", action="store_true")
    a = ap.parse_args(); src = pathlib.Path(a.rtf).expanduser()
    paras, notes = convert(src.read_bytes())
    md = to_markdown(paras, notes)
    out = pathlib.Path(a.output).expanduser() if a.output else src.with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    heads = [(i, s, t) for i, (s, t) in enumerate(paras) if 1 <= s <= 9 or s == 53]
    words = len(md.split()); pages = len(re.findall(r"(?m)^\[\d{1,4}\]$", md))
    print(f"  {src.name}: {len(paras)} paragraphs, {words} words, {len(heads)} headings, {len(notes)} footnotes, {pages} page markers → {out}")
    if a.list_headings:
        for i, s, t in heads: print(f"  [{i:4d}] {'#' * (s if s <= 9 else 1):4s} {t[:100]}")


if __name__ == "__main__": main()
