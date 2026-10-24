# -*- coding: utf-8 -*-
"""Rebuild blank-line-delimited paragraphs from a PDF with a text layer whose body is justified
(a LibreOffice/Word re-typesetting, a journal offprint, a modern book PDF).

    python3 /SKILL_BASE/scripts/pdf_bbox_paras.py /abs/path/book.pdf -o /SCRATCHPAD/orig.txt [--right 490] [--left 86]

Runs `pdftotext -bbox-layout` (poppler) and applies three geometric rules that a plain `pdftotext`
dump cannot: a body line that stops short of the right margin AND ends in terminal punctuation
closes a paragraph; a line that starts right of the left margin opens one (list items, indents);
a line with no lowercase letters is a heading (a two-line caps heading is joined). End-of-line
hyphens are joined when the next word is lowercase. Every page start is written inline as `[n]`
before the first word of that page (n = PDF page), mid-paragraph or not — the aligner and
build_pdf.py carry `[n]` markers into both columns.

Prints the paragraph count and every paragraph under 130 characters (headings, list items,
fragments) so false splits and glued headings are visible at once. It does not correct OCR-style
typos in the text layer — do that chunk by chunk with fix_orig.py while translating.

--right / --left are the x-coordinates (points) of the body's right and left margins; the defaults
suit US letter with 1-inch-ish margins. Read them off the histogram the script prints with --probe.
"""
import re, sys, html, argparse, subprocess, collections, pathlib

ap = argparse.ArgumentParser()
ap.add_argument('pdf'); ap.add_argument('-o', '--output', required=True)
ap.add_argument('--right', type=float, default=None, help='x below which a line is a paragraph end (default: modal xMax - 7)')
ap.add_argument('--left', type=float, default=None, help='body left margin x (default: modal xMin)')
ap.add_argument('--probe', action='store_true', help='print the xMin/xMax histograms and exit')
a = ap.parse_args()

src = subprocess.run(['pdftotext', '-bbox-layout', a.pdf, '-'], capture_output=True, text=True, check=True).stdout
pages = re.findall(r'<page[^>]*>(.*?)</page>', src, re.S)
LINE = re.compile(r'<line xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"[^>]*>(.*?)</line>', re.S)
allx = [(float(x1), float(x2)) for pg in pages for x1, x2, _ in LINE.findall(pg)]
cmin = collections.Counter(int(x) for x, _ in allx); cmax = collections.Counter(int(x) for _, x in allx)
LEFT = a.left if a.left is not None else float(cmin.most_common(1)[0][0])
RIGHT = a.right if a.right is not None else float(cmax.most_common(1)[0][0]) - 7
if a.probe:
    print('xMin (most common):', cmin.most_common(6)); print('xMax (most common):', cmax.most_common(6))
    print(f'→ using LEFT={LEFT} RIGHT={RIGHT}'); sys.exit(0)

END = re.compile(r'[.!?:;"”»)\]…]\s*$')
CAPS = re.compile(r'^[^a-záéíóúñüàèìòùâêîôûäöëïç]*$')
out, cur, cur_caps = [], [], False
def flush():
    global cur
    if cur: out.append(' '.join(cur)); cur = []
for pn, pg in enumerate(pages, 1):
    marker = f'[{pn}]'
    for xmin, xmax, body in LINE.findall(pg):
        xmin, xmax = float(xmin), float(xmax)
        words = [html.unescape(w) for w in re.findall(r'<word[^>]*>(.*?)</word>', body)]
        if not words: continue
        text = ' '.join(words)
        caps = bool(CAPS.match(text)) and len(re.findall(r'[A-ZÁÉÍÓÚÑÜ]', text)) >= 3
        if caps:
            if cur and not cur_caps: flush()
            cur.append((marker + ' ' if marker else '') + text); marker = ''; cur_caps = True
            if xmax < RIGHT: flush(); cur_caps = False
            continue
        if cur_caps: flush(); cur_caps = False
        if xmin > LEFT + 8: flush()
        if cur and cur[-1].endswith('-') and len(cur[-1]) > 2 and cur[-1][-2].isalpha() and words[0][:1].islower():
            cur[-1] = cur[-1][:-1] + words[0]; words = words[1:]
        if marker and words: words = [marker + ' ' + words[0]] + words[1:]; marker = ''
        cur.extend(words)
        if xmax < RIGHT and END.search(text): flush()
flush()
pathlib.Path(a.output).write_text('\n\n'.join(out) + '\n', encoding='utf-8')
print(f'{len(out)} paragraphs; {sum(len(p.split()) for p in out)} words; {len(pages)} page markers → {a.output}')
print('paragraphs under 130 characters (headings, list items, fragments):')
for i, p in enumerate(out):
    if len(p) < 130: print(f'  [{i}] {p}')
