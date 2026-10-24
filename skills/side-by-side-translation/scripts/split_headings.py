#!/usr/bin/env python3
"""Split embedded structural headings out of body paragraphs.

Usage:
    python3 split_headings.py orig.txt [trans.txt] [--dry-run] [--report]

Detects headings embedded at the start or end of body paragraphs and splits
them into standalone paragraphs. Operates on both orig.txt and trans.txt
in tandem to keep them aligned.

Detected patterns (in order of priority):
  - § sections:     "§ 6. Der Grundsatz als ..."  (at start of paragraph)
  - KAPITEL/TEIL:   "ERSTES KAPITEL" / "Erster Teil" (at start or end)
  - ALL-CAPS lines: "ZWISCHENBETRACHTUNG" (short, all-caps, at start or end)
  - a)-z) labels:   "a) Die Bestimmung ..." (at start of paragraph)
  - Roman numerals: "III. Die Frage ..." (at start of paragraph)

When trans.txt is provided, the script looks for the corresponding marker in
the translation paragraph at the same index. If no marker is found in the
translation, it inserts the German marker as a standalone heading (the
translator can fix it later).

With --dry-run, prints what it would do without modifying files.
With --report, prints a machine-readable list of splits for review.
"""

import re
import sys
import pathlib


def load_paragraphs(path):
    text = pathlib.Path(path).read_text(encoding='utf-8')
    return [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]


def save_paragraphs(path, paras):
    pathlib.Path(path).write_text(
        '\n\n'.join(paras) + '\n', encoding='utf-8'
    )


# --- Detection patterns ---

# § section at start: "§ 6. Title here Body text continues..."
RE_SECTION_START = re.compile(
    r'^(§\s*\d+\.?\s+[^\n]{3,80}?(?:\.\s|\s*$))([\s\S]+)',
    re.MULTILINE
)

# KAPITEL / TEIL / CHAPTER at start or end
RE_KAPITEL = re.compile(
    r'((?:ERSTES|ZWEITES|DRITTES|VIERTES|FÜNFTES|SECHSTES)\s+KAPITEL'
    r'|(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+CHAPTER'
    r'|(?:Erster|Zweiter|Dritter|Vierter|Fünfter)\s+Teil'
    r'|(?:First|Second|Third|Fourth|Fifth)\s+Part'
    r'|ZWISCHENBETRACHTUNG|INTERIM\s+REFLECTION)',
    re.IGNORECASE
)

# ALL-CAPS short string (3-80 chars, at least 2 uppercase letters)
def is_allcaps_heading(s):
    s = s.strip()
    return (3 <= len(s) <= 80
            and s == s.upper()
            and sum(1 for c in s if c.isalpha() and c.isupper()) >= 2
            and not re.match(r'^\[\d+\]$', s))  # not a page marker

# a)-z) subsection at start
RE_SUBSECTION_START = re.compile(
    r'^([a-zα-ω]\)\s+[^\n]{3,120}?(?:\.\s|\s*$))([\s\S]+)',
    re.MULTILINE
)

# Roman numeral heading at start
RE_ROMAN_START = re.compile(
    r'^((?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.\s+[^\n]{3,100}?\.?\s*$)([\s\S]+)',
    re.MULTILINE
)


def find_split(para):
    """Return (heading, body, position) or None.

    position is 'start' or 'end' — where the heading was found.
    """
    # § section at start
    m = RE_SECTION_START.match(para)
    if m:
        head = m.group(1).strip()
        body = m.group(2).strip()
        if body and len(body) > 20:
            return (head, body, 'start')

    # KAPITEL/TEIL at start of paragraph
    lines = para.split('\n')
    first_line = lines[0].strip() if lines else ''
    if RE_KAPITEL.match(first_line) and len(lines) > 1:
        head = first_line
        body = '\n'.join(lines[1:]).strip()
        if body:
            return (head, body, 'start')

    # KAPITEL/TEIL at end of paragraph (glued to previous body)
    last_line = lines[-1].strip() if lines else ''
    if RE_KAPITEL.match(last_line) and len(lines) > 1:
        body = '\n'.join(lines[:-1]).strip()
        head = last_line
        if body:
            return (head, body, 'end')

    # ALL-CAPS heading at start (first sentence, if short and all-caps)
    if first_line and is_allcaps_heading(first_line) and len(lines) > 1:
        body = '\n'.join(lines[1:]).strip()
        if body and len(body) > 20:
            return (first_line, body, 'start')

    # ALL-CAPS heading at end
    if last_line and is_allcaps_heading(last_line) and len(lines) > 1:
        body = '\n'.join(lines[:-1]).strip()
        if body and len(body) > 20:
            return (last_line, body, 'end')

    # a)-z) subsection at start
    m = RE_SUBSECTION_START.match(para)
    if m:
        head = m.group(1).strip()
        body = m.group(2).strip()
        if body and len(body) > 20:
            return (head, body, 'start')

    # Roman numeral at start
    m = RE_ROMAN_START.match(para)
    if m:
        head = m.group(1).strip()
        body = m.group(2).strip()
        if body and len(body) > 20:
            return (head, body, 'start')

    return None


def find_corresponding_split(trans_para, de_heading, position):
    """Try to find the same structural marker in the translation paragraph."""
    # For § markers, look for § N at start
    m = re.match(r'^(§\s*\d+)', de_heading)
    if m:
        sec_num = m.group(1)
        tm = re.match(
            rf'^({re.escape(sec_num)}\.?\s+[^\n]{{3,120}}?(?:\.\s|\s*$))([\s\S]+)',
            trans_para, re.MULTILINE
        )
        if tm:
            return (tm.group(1).strip(), tm.group(2).strip())

    # For KAPITEL/CHAPTER patterns
    if RE_KAPITEL.match(de_heading):
        lines = trans_para.split('\n')
        if position == 'start' and lines:
            first = lines[0].strip()
            if RE_KAPITEL.match(first) or is_allcaps_heading(first):
                body = '\n'.join(lines[1:]).strip()
                if body:
                    return (first, body)
        if position == 'end' and lines:
            last = lines[-1].strip()
            if RE_KAPITEL.match(last) or is_allcaps_heading(last):
                body = '\n'.join(lines[:-1]).strip()
                if body:
                    return (last, body)

    # ALL-CAPS: look for matching ALL-CAPS line at same position
    if is_allcaps_heading(de_heading):
        lines = trans_para.split('\n')
        if position == 'start' and lines and is_allcaps_heading(lines[0].strip()):
            return (lines[0].strip(), '\n'.join(lines[1:]).strip())
        if position == 'end' and lines and is_allcaps_heading(lines[-1].strip()):
            return (lines[-1].strip(), '\n'.join(lines[:-1]).strip())

    # a)-z) subsection: look for same letter at start
    m = re.match(r'^([a-zα-ω])\)', de_heading)
    if m:
        letter = m.group(1)
        tm = re.match(
            rf'^({re.escape(letter)}\)\s+[^\n]{{3,120}}?(?:\.\s|\s*$))([\s\S]+)',
            trans_para, re.MULTILINE
        )
        if tm:
            return (tm.group(1).strip(), tm.group(2).strip())

    # Roman numeral: look for same numeral
    m = re.match(r'^(XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.', de_heading)
    if m:
        numeral = m.group(1)
        tm = re.match(
            rf'^({re.escape(numeral)}\.\s+[^\n]{{3,100}}?\.?\s*$)([\s\S]+)',
            trans_para, re.MULTILINE
        )
        if tm:
            return (tm.group(1).strip(), tm.group(2).strip())

    # Fallback: use the German heading as-is for the translation too
    return None


def process(orig_path, trans_path=None, dry_run=False, report=False):
    orig = load_paragraphs(orig_path)
    trans = load_paragraphs(trans_path) if trans_path else None

    if trans and len(orig) != len(trans):
        print(f"ERROR: paragraph count mismatch: orig={len(orig)}, trans={len(trans)}")
        sys.exit(1)

    new_orig = []
    new_trans = [] if trans else None
    splits = []

    for i, para in enumerate(orig):
        result = find_split(para)
        if result is None:
            new_orig.append(para)
            if trans:
                new_trans.append(trans[i])
            continue

        heading, body, position = result

        # Find corresponding split in translation
        if trans:
            t_result = find_corresponding_split(trans[i], heading, position)
            if t_result:
                t_heading, t_body = t_result
            else:
                # No corresponding marker found — use DE heading for EN too
                t_heading = heading
                t_body = trans[i]

        if position == 'start':
            new_orig.append(heading)
            new_orig.append(body)
            if trans:
                new_trans.append(t_heading)
                new_trans.append(t_body)
        else:  # 'end'
            new_orig.append(body)
            new_orig.append(heading)
            if trans:
                new_trans.append(t_body)
                new_trans.append(t_heading)

        splits.append({
            'index': i,
            'position': position,
            'heading': heading[:60],
            'body_preview': body[:40] + '...'
        })

    if report or dry_run:
        print(f"Found {len(splits)} embedded headings to split:")
        for s in splits:
            print(f"  [{s['index']}] ({s['position']}) {s['heading']}")
            print(f"       body: {s['body_preview']}")
        print(f"\nWould produce {len(new_orig)} paragraphs (was {len(orig)})")
        if dry_run:
            return

    if not splits:
        print("No embedded headings found. Files unchanged.")
        return

    save_paragraphs(orig_path, new_orig)
    print(f"Wrote {len(new_orig)} paragraphs to {orig_path} (was {len(orig)})")

    if trans:
        save_paragraphs(trans_path, new_trans)
        print(f"Wrote {len(new_trans)} paragraphs to {trans_path} (was {len(trans)})")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('orig', help='Path to orig.txt')
    parser.add_argument('trans', nargs='?', help='Path to trans.txt (optional)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print what would be split without modifying files')
    parser.add_argument('--report', action='store_true',
                        help='Print split report (still modifies files unless --dry-run)')
    args = parser.parse_args()

    process(args.orig, args.trans,
            dry_run=args.dry_run,
            report=args.report)
