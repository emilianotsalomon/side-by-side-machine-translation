#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_missing.py — insert translated paragraphs into a translation file where align_check found gaps.

    python3 apply_missing.py TRANS.md DIR/missing.json

Each entry of missing.json (written by align_check.py) carries `after_trans` — the first 80
characters of the translation paragraph that precedes the gap — and a `trans` field to fill
(an empty `trans` is skipped and reported). The new paragraph goes right after that anchor,
in the file's own style (one paragraph per line, or blank-line separated). Entries are applied
from the end of the file backwards, so several gaps can be filled in one run."""
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from md_prep import _inline

p = pathlib.Path(sys.argv[1]).expanduser(); items = json.load(open(sys.argv[2], encoding="utf-8"))
raw = p.read_text(encoding="utf-8"); lines = raw.split("\n")
norm = [_inline(l) for l in lines]
blank_style = sum(1 for l in lines if not l.strip()) > len(lines) * 0.3
todo = [it for it in items if it.get("trans", "").strip()]; skipped = [it for it in items if not it.get("trans", "").strip()]
placed = []; failed = []
for it in sorted(todo, key=lambda x: -x["i"]):
    anc = _inline(it["after_trans"] or "")[:60]
    idx = next((k for k, l in enumerate(norm) if anc and l.startswith(anc)), None) if anc else -1
    if idx is None: failed.append(it); continue
    ins = it["trans"].strip()
    if blank_style: lines[idx + 1:idx + 1] = ["", ins]
    else: lines.insert(idx + 1, ins)
    norm = [_inline(l) for l in lines]; placed.append(it)
p.write_text("\n".join(lines), encoding="utf-8")
print(f"  {len(placed)} paragraph(s) inserted into {p.name}" + (f"; {len(skipped)} still untranslated (empty 'trans')" if skipped else "") + (f"; {len(failed)} anchor(s) not found: " + ", ".join(str(it['i']) for it in failed) if failed else ""))
