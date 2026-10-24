# -*- coding: utf-8 -*-
"""Append translated paragraphs (stdin, blank-line-delimited) to trans.txt.

    python3 /SKILL_BASE/scripts/append_trans.py /SCRATCHPAD/trans.txt 12 --orig /SCRATCHPAD/orig.txt <<'EOF'
    ...translations of orig paragraphs 12, 13, ... in order...
    EOF

Refuses the chunk unless trans.txt currently holds exactly START paragraphs, so a
skipped or doubled chunk is caught immediately, not at --verify time. With --orig
it also checks that a leading footnote/heading anchor "(N)", "N." or "IV." on each
new paragraph matches the source paragraph at the same index, and that the chunk
does not run past the end of the source."""
import sys, re, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from append_pairs import _ANCHOR
ap = argparse.ArgumentParser(); ap.add_argument('trans'); ap.add_argument('start', type=int); ap.add_argument('--orig'); a = ap.parse_args()
split = lambda t: [x.strip() for x in re.split(r'\n\s*\n', t) if x.strip()]
new = split(sys.stdin.read())
p = pathlib.Path(a.trans); old = split(p.read_text(encoding='utf-8')) if p.exists() else []
if len(old) != a.start: sys.exit(f'refused: {a.trans} holds {len(old)} paragraphs, expected {a.start}')
if a.orig:
    O = split(pathlib.Path(a.orig).read_text(encoding='utf-8'))
    if a.start + len(new) > len(O): sys.exit(f'refused: chunk ends at {a.start+len(new)} but source has {len(O)} paragraphs')
    for k, t in enumerate(new):
        ao, at = _ANCHOR.match(O[a.start+k]), _ANCHOR.match(t)
        if (ao and ao.group(0)) != (at and at.group(0)):
            sys.exit(f'refused: anchor mismatch at [{a.start+k}]: {O[a.start+k][:40]!r} vs {t[:40]!r}')
p.write_text('\n\n'.join(old + new) + '\n', encoding='utf-8')
print(f'{len(new)} added; {a.trans} now {len(old)+len(new)} paragraphs' + (f' of {len(O)}' if a.orig else ''))
