# -*- coding: utf-8 -*-
'''Append one aligned chunk to orig.txt and trans.txt.

Guarantees paragraph-count parity chunk by chunk, so --verify passes at the end
instead of failing on a 600-paragraph file. Also checks that any leading footnote
marker "(N)" or Roman/Arabic heading number matches between the two columns.

Usage (from a heredoc; keep the coding line, it prevents non-UTF-8 stdin errors):

    python3 - <<'PYEOF'
    # -*- coding: utf-8 -*-
    import sys; sys.path.insert(0, '/SKILL_BASE/scripts')
    from append_pairs import append
    O = ["""Primer párrafo…""", """(3) Nota…"""]
    T = ["""First paragraph…""", """(3) Note…"""]
    append('/SCRATCHPAD/orig.txt', '/SCRATCHPAD/trans.txt', O, T)
    PYEOF
'''
import pathlib, re, sys

_ANCHOR = re.compile(r'^(?:\((\d+)\)|(\d{1,2})\.|((?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I))\.)\s')

def _norm(s):
    return re.sub(r'\s*\n\s*', ' ', s.strip())

def append(orig_path, trans_path, O, T):
    if len(O) != len(T):
        sys.exit(f"count mismatch: {len(O)} original vs {len(T)} translated paragraphs")
    for i, (o, t) in enumerate(zip(O, T)):
        ao, at = _ANCHOR.match(o.strip()), _ANCHOR.match(t.strip())
        if (ao and ao.group(0)) != (at and at.group(0)):
            sys.exit(f"anchor mismatch at chunk index {i}: {o.strip()[:40]!r} vs {t.strip()[:40]!r}")
    for path, L in ((orig_path, O), (trans_path, T)):
        p = pathlib.Path(path)
        old = p.read_text(encoding='utf-8') if p.exists() else ''
        txt = '\n\n'.join(_norm(s) for s in L)
        p.write_text((old.rstrip('\n') + '\n\n' + txt) if old.strip() else txt, encoding='utf-8')
    n = len([b for b in re.split(r'\n\n+', pathlib.Path(orig_path).read_text(encoding='utf-8')) if b.strip()])
    print(f"{len(O)} added; total {n} paragraphs")
