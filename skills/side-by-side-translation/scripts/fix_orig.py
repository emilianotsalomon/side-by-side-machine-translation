# -*- coding: utf-8 -*-
"""Apply exact-string (or regex) corrections to a text/Markdown file. Stdin: JSON list of [old, new].

    python3 /SKILL_BASE/scripts/fix_orig.py /SCRATCHPAD/orig.txt <<'EOF'
    [["Piaton", "Platon"],
     ["vor Augen hält Blicken", "vor Augen hält. Blicken"],
     ["ertränken. Der Schlaf als Lebensform. —", "ertränken.\\n\\nDer Schlaf als Lebensform. —"]]
    EOF
    python3 fix_orig.py BOOK.md --regex '^## ' '# '            # one regex fix (Python re, MULTILINE)
    python3 fix_orig.py BOOK.md --regex < fixes.json            # every pair is a regex pattern → replacement

Every `old` must occur at least once (aborts before writing otherwise), so a typo in the fix
list cannot silently do nothing. A `new` containing "\\n\\n" splits a paragraph; run it BEFORE
appending the translation of that region so the indices stay in step. On a Markdown file the
`old` strings must match the RAW Markdown (`# ` prefixes, `**`, `\\-`), not the normalised text."""
import sys, json, pathlib, re
args = sys.argv[1:]; regex = "--regex" in args
if regex: args.remove("--regex")
p = pathlib.Path(args[0]); s = p.read_text(encoding='utf-8')
pairs = [[args[1], args[2]]] if len(args) == 3 else json.load(sys.stdin)
if regex:
    missing = [o for o, _ in pairs if not re.search(o, s, re.M)]
    if missing: sys.exit('no match, nothing written: ' + '; '.join(repr(m[:50]) for m in missing))
    total = 0
    for o, n in pairs: s, k = re.subn(o, n, s, flags=re.M); total += k
    p.write_text(s, encoding='utf-8'); print(f'{len(pairs)} regex fixes, {total} replacements; {len([x for x in s.split(chr(10)+chr(10)) if x.strip()])} paragraphs')
else:
    missing = [o for o, _ in pairs if o not in s]
    if missing: sys.exit('not found, nothing written: ' + '; '.join(repr(m[:50]) for m in missing))
    for o, n in pairs: s = s.replace(o, n)
    p.write_text(s, encoding='utf-8')
    print(f'{len(pairs)} fixes applied; {len([x for x in s.split(chr(10)+chr(10)) if x.strip()])} paragraphs')
