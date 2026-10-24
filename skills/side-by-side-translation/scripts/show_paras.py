# -*- coding: utf-8 -*-
"""Print paragraphs [START, END) of a blank-line-delimited file with their indices.

    python3 /SKILL_BASE/scripts/show_paras.py /SCRATCHPAD/orig.txt 12 27
    python3 /SKILL_BASE/scripts/show_paras.py book.ocr.md 12 27            # .md: normalised as md_prep does
    python3 /SKILL_BASE/scripts/show_paras.py translation.md 12 27 --side trans

Stops early when --max-chars (default 30000) is reached and tells you where to
resume: tool output much beyond that is dumped to a file instead of shown.
A Markdown file is shown as the aligner sees it (headings unprefixed, notes as (n),
standalone page blocks left out), so the indices match build_pdf.py --list except
where the aligner merged a paragraph the page break had split."""
import sys, re, pathlib, argparse
ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('start', type=int); ap.add_argument('end', type=int)
ap.add_argument('--max-chars', type=int, default=30000)
ap.add_argument('--side', choices=['orig', 'trans'], default=None, help=".md only: normalise as the original (default) or as the translation (guessed from a file name containing 'trans')")
a = ap.parse_args()
path = pathlib.Path(a.file); text = path.read_text(encoding='utf-8')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from md_prep import MD_SUFFIXES, normalize_md
if path.suffix.lower() in MD_SUFFIXES:
    text, _ = normalize_md(text, side=a.side or ('trans' if 'trans' in path.stem.lower() else 'orig'))
    text = re.sub(r'(?m)^\[(?:p\.\s*)?(?:\d{1,4}|[ivxlc]{1,6})\]\n\n', '', text)   # standalone page blocks are not paragraphs
ps = [p for p in re.split(r'\n\n+', text) if p.strip()]
used = 0
for i in range(a.start, min(a.end, len(ps))):
    if used + len(ps[i]) > a.max_chars and i > a.start:
        print(f'… stopped before [{i}] (char budget); resume with start={i}'); break
    print(f'[{i}] {ps[i]}\n'); used += len(ps[i])
else:
    print(f'-- shown up to [{min(a.end, len(ps))-1}] of {len(ps)} paragraphs')
