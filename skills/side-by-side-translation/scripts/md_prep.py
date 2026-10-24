#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_prep.py — normalise a Markdown source (.md) into the skill's blank-line paragraph text.

Both builders (side_by_side_html.py, build_pdf.py) call this automatically for any `.md` /
`.markdown` input, so a Markdown OCR and a Markdown translation can be aligned and rendered
without a hand-made .txt conversion. Two Markdown shapes are handled:

  * OCR Markdown (the `ocr` tool, HathiTrust-style exports): `[n]` page markers standalone or
    inline, `#`/`##` headings, `[^n]` note references and `[^n]: text` note bodies, blank-line
    paragraphs.
  * LLM translation Markdown (Qwen / GPT / Claude output): a chatty preamble, `**[n]**` page
    blocks, one paragraph per line, `*(Title Page / Blank)*` placeholders, **bold** / *italic*.

Rules (everything applied is listed in the report):
  - `#` headings → standalone paragraphs; the `#` count is kept as the heading level (`md_level`,
    used by build_pdf.py for the heading level and by --toc for the sidebar level).
  - `[^n]: text` → a `(n) text` note paragraph; inline `[^n]` → `(n)`.
  - one line = one paragraph, unless the previous line ends mid-sentence (a soft wrap) or with a
    hyphen — then the lines are joined.
  - standalone page markers (`[12]`, `**[12]**`, `[p. 12]`): kept as `[n]` blocks for the original
    (the aligner turns them into page_after / page_mid); DROPPED for the translation (side='trans'),
    whose pagination is derived from the original — an LLM's page blocks rarely match the book.
  - dropped: LLM preamble / postamble lines, `*(… blank …)*` placeholders, horizontal rules, images.
  - stripped: **bold**, *italic*, `code`, [link](url) → link, backslash escapes (`\\-`), `- ` bullets.
  - suspicious headings (garbled OCR: too short, lowercase, no vowel) are REPORTED, not removed:
    fix them in the .md with fix_orig.py — the builders re-normalise on every run, so the .md stays
    the single source of truth.

    python3 md_prep.py FILE.md [--side orig|trans] [-o out.txt] [--json]
"""
from __future__ import annotations
import argparse, json, os, pathlib, re

MD_SUFFIXES = ('.md', '.markdown', '.mdown')

_PAGE_ALONE = re.compile(r'^\s*(?:\*\*|__|\*|_)?\s*\[(?:p\.\s*)?(\d{1,4}|[ivxlc]{1,6})\]\s*(?:\*\*|__|\*|_)?\s*:?\s*$')
_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_FN_DEF = re.compile(r'^\[\^([^\]]+)\]:\s*(.*)$')
_FN_REF = re.compile(r'\[\^([^\]]+)\]')
_HR = re.compile(r'^\s*(?:[-*_]\s*){3,}$')
_IMG = re.compile(r'!\[[^\]]*\]\([^)]*\)')
_LINK = re.compile(r'\[([^\]]+)\]\((?:[^)\s]+)(?:\s+"[^"]*")?\)')
_ESC = re.compile(r'\\([\\`*_{}\[\]()#+\-.!|>~])')
_BULLET = re.compile(r'^\s*[-*+]\s+(?=\S)')
_CODE_FENCE = re.compile(r'^\s*(?:```|~~~)')
_PREAMBLE = re.compile(r"^(?:here (?:is|are)\b|below is\b|the following is\b|this is (?:the|a|my) (?:complete |full |requested )?translation\b|sure[,!]|certainly[,!]|of course[,!]|okay[,!]|i have translated\b|i've translated\b)", re.I)
_POSTAMBLE = re.compile(r"^(?:let me know\b|i hope this\b|feel free\b|if you (?:need|want|would like)\b|\(?end of (?:the )?(?:translation|text|document)\)?\.?$|would you like\b)", re.I)
_PLACEHOLDER_WORDS = re.compile(r'\b(?:blank|title page|half[- ]title|illegible|empty|no text|image|illustration|figure|plate|untranslatable|intentionally left)\b', re.I)
_TERMINAL = re.compile(r'[.!?…:;"”»’\')\]]\s*$')


def _strip_emphasis(s: str) -> str:
    s = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'\1', s)
    s = re.sub(r'__(?=\S)(.+?)(?<=\S)__', r'\1', s)
    # SBS_MD_ITALICS=1 (build_pdf --md-italics): keep *single-star* emphasis as private-use
    # sentinels U+E000…U+E001, which build_pdf turns into <i>…</i> after escaping
    s = re.sub(r'(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])',
               ('\ue000\\1\ue001' if os.environ.get("SBS_MD_ITALICS") else r'\1'), s)
    s = re.sub(r'(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    return s


def _inline(s: str) -> str:
    s = _IMG.sub('', s)
    s = _LINK.sub(r'\1', s)
    s = _strip_emphasis(s)
    s = _ESC.sub(r'\1', s)
    s = _FN_REF.sub(r'(\1)', s)
    s = _BULLET.sub('', s)
    s = s.replace(' ', ' ')
    return re.sub(r'[ \t]+', ' ', s).strip()


_NUMBERED_HEAD = re.compile(r'^(?:\[[^\]]{1,8}\]\s*)?(?:§\s*\d+|(?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.|\d{1,2}\.|[a-z]\))\s+\S')


def _heading_like(t: str) -> bool:
    """A short ALL-CAPS line, or a short numbered title: never joined to its neighbours."""
    core = re.sub(r'^\s*(?:\[[^\]]{1,8}\]\s*)+', '', t)
    letters = sum(c.isalpha() for c in core)
    if len(core) <= 120 and letters >= 3 and core == core.upper(): return True
    if len(core) <= 120 and _NUMBERED_HEAD.match(core) and not _TERMINAL.search(core): return True
    return False


def _continues(prev: str, nxt: str) -> str | None:
    """How the next line attaches to the previous one: 'hyphen', 'space', or None (new paragraph).
    Markdown prose is either one paragraph per line (LLM output) or soft-wrapped; a line that ends
    mid-sentence continues, a heading-like line never does, and a short unpunctuated line followed
    by a capital is a title or a fragment, not a wrap."""
    if _heading_like(prev) or _heading_like(nxt): return None
    if re.search(r'\w-$', prev) and nxt[:1].islower(): return 'hyphen'
    if not _TERMINAL.search(prev) and (nxt[:1].islower() or len(prev) >= 60): return 'space'
    return None


def _suspicious_heading(t: str) -> str | None:
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 3: return 'fewer than 3 letters'
    if t == t.lower(): return 'no capital letter'
    if not re.search(r'[aeiouáéíóúàèìòùäöüAEIOUÁÉÍÓÚÄÖÜ]', t): return 'no vowel'
    if len(t) < 5: return 'very short'
    return None


def normalize_md(text: str, side: str = 'orig') -> tuple[str, dict]:
    """→ (blank-line paragraph text, report). side='trans' drops standalone page markers."""
    text = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)                 # HTML comments (tool markers) are not text
    if text.startswith('---\n'):                       # YAML front matter
        end = text.find('\n---', 4)
        if end > 0: text = text[end + 4:]
    units: list[dict] = []
    dropped: list[tuple[str, str]] = []
    cur: dict | None = None
    in_fence = False

    def flush():
        nonlocal cur
        if cur is not None and cur['text'].strip(): units.append(cur)
        cur = None

    for raw in text.split('\n'):
        line = raw.rstrip()
        if _CODE_FENCE.match(line): in_fence = not in_fence; flush(); continue
        if in_fence: continue
        if not line.strip(): flush(); continue
        if _HR.match(line): flush(); dropped.append(('rule', line.strip())); continue
        m = _PAGE_ALONE.match(line)
        if m:
            flush()
            if side == 'trans': dropped.append(('page marker (translation)', line.strip()))
            else: units.append({'kind': 'page', 'text': f'[{m.group(1)}]'})
            continue
        m = _HEADING.match(line)
        if m:
            flush(); t = _inline(m.group(2))
            if t: units.append({'kind': 'heading', 'level': len(m.group(1)), 'text': t})
            continue
        m = _FN_DEF.match(line)
        if m:
            flush(); cur = {'kind': 'note', 'text': f'({m.group(1)}) ' + _inline(m.group(2))}
            continue
        t = _inline(line)
        if not t: continue
        how = _continues(cur['text'], t) if cur is not None and cur['kind'] in ('text', 'note') else None
        if how == 'hyphen': cur['text'] = cur['text'][:-1] + t
        elif how == 'space': cur['text'] += ' ' + t
        else: flush(); cur = {'kind': 'text', 'text': t}
    flush()

    # placeholders such as *(Title Page / Blank)*
    kept = []
    for u in units:
        t = u['text']
        if u['kind'] == 'text' and len(t) <= 80 and re.fullmatch(r'[(\[].*[)\]]', t) and _PLACEHOLDER_WORDS.search(t):
            dropped.append(('placeholder', t)); continue
        kept.append(u)
    units = kept
    # LLM preamble / postamble
    while units and units[0]['kind'] == 'text' and (_PREAMBLE.match(units[0]['text']) or (units[0]['text'].endswith(':') and re.search(r'translat', units[0]['text'], re.I))):
        dropped.append(('preamble', units.pop(0)['text']))
    while units and units[-1]['kind'] == 'text' and _POSTAMBLE.match(units[-1]['text']):
        dropped.append(('postamble', units.pop()['text']))

    out = '\n\n'.join(u['text'] for u in units) + '\n'
    paras = [u for u in units if u['kind'] != 'page']
    report = {
        'side': side,
        'paragraphs': len(paras),
        'pages_kept': sum(1 for u in units if u['kind'] == 'page'),
        'pages_dropped': sum(1 for r, _ in dropped if r.startswith('page marker')),
        'inline_markers': len(re.findall(r'(?<!^)\[(?:p\.\s*)?(?:\d{1,4}|[ivxlc]{1,6})\]', out, re.M)),
        'headings': [(i, u['level'], u['text']) for i, u in enumerate(paras) if u['kind'] == 'heading'],
        'levels': {u['text']: u['level'] for u in units if u['kind'] == 'heading'},
        'notes': sum(1 for u in units if u['kind'] == 'note'),
        'dropped': [(r, t[:70]) for r, t in dropped if not r.startswith('page marker')],
        'suspicious_headings': [(i, u['text'], _suspicious_heading(u['text'])) for i, u in enumerate(paras) if u['kind'] == 'heading' and _suspicious_heading(u['text'])],
        'leftover_backslashes': sum(1 for u in units if '\\' in u['text']),
    }
    return out, report


def summary(report: dict, name: str = '') -> str:
    r = report; lines = [f"  Markdown {r['side']}: {name} → {r['paragraphs']} paragraphs, {len(r['headings'])} headings, {r['notes']} notes"
                          + (f", {r['pages_kept']} page blocks kept" if r['pages_kept'] else '')
                          + (f", {r['pages_dropped']} page blocks dropped (pagination comes from the original)" if r['pages_dropped'] else '')
                          + (f", {r['inline_markers']} inline markers" if r['inline_markers'] else '')]
    for reason, t in r['dropped']: lines.append(f"    dropped {reason}: {t!r}")
    for i, t, why in r['suspicious_headings']: lines.append(f"    [!] heading [{i}] {t!r} looks like OCR debris ({why}) — fix or delete it in the .md with fix_orig.py")
    if r['leftover_backslashes']: lines.append(f"    [!] {r['leftover_backslashes']} paragraph(s) still contain a backslash (OCR debris such as \\12.)")
    return '\n'.join(lines)


def is_md(path) -> bool:
    return pathlib.Path(path).suffix.lower() in MD_SUFFIXES


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--side', choices=['orig', 'trans'], default='orig')
    ap.add_argument('-o', '--output', help='write the normalised text here (default: print the report only)')
    ap.add_argument('--json', action='store_true', help='print the report as JSON')
    a = ap.parse_args()
    text, rep = normalize_md(pathlib.Path(a.file).read_text(encoding='utf-8'), side=a.side)
    if a.output: pathlib.Path(a.output).expanduser().write_text(text, encoding='utf-8')
    print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else summary(rep, pathlib.Path(a.file).name))
    if a.output: print(f"  → {a.output}")


if __name__ == '__main__': main()
