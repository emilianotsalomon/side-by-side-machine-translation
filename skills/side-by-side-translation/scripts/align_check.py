#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""align_check.py — diagnose the paragraph alignment of an original and its translation in ONE call.

    python3 align_check.py ORIG.md TRANS.md [--emit DIR] [--show 40] [--band 80]

Order-preserving alignment (1:1, 1:0, 0:1, up to 6:1 and 1:3 moves) on the normalised paragraphs
(Markdown is normalised as md_prep does; .txt is read as is). Prints a compact report — only the
rows that are NOT one-to-one, ~100 characters a side, with a hint — and, with --emit DIR, writes:

  DIR/alignment.json   every row (indices, lengths, ratio, hint)
  DIR/missing.json     source paragraphs with no translation: fill each "trans", then
                       `apply_missing.py TRANS.md DIR/missing.json`
  DIR/fixes_orig.json  auto-proposed merges of OCR-split source paragraphs → `fix_orig.py ORIG.md < it`
  DIR/fixes_trans.json auto-proposed merges of translator-split paragraphs → `fix_orig.py TRANS.md < it`

Exit 0 when every row is one-to-one (then side_by_side_html.py --verify is the last word), 1 otherwise.
Rows that are not auto-fixable are printed with both raw boundaries so one fix_orig.py list settles them."""
from __future__ import annotations
import argparse, json, pathlib, re, sys, unicodedata
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from md_prep import MD_SUFFIXES, normalize_md

PAGE_ALONE = re.compile(r"^\[(?:p\.\s*)?(\d{1,4}|[ivxlc]{1,6})\]$")
TERMINAL = re.compile(r"[.!?…:;\"”»’')\]]\s*$")


def load(path: pathlib.Path, side: str):
    raw = path.read_text(encoding="utf-8")
    text = normalize_md(raw, side=side)[0] if path.suffix.lower() in MD_SUFFIXES else raw
    paras, pages, pg = [], [], None
    for b in re.split(r"\n\s*\n", text):
        b = b.strip()
        if not b: continue
        m = PAGE_ALONE.match(b)
        if m: pg = m.group(1); continue
        for mm in re.finditer(r"\[(\d{1,4})\]", b): pg = mm.group(1)
        paras.append(b); pages.append(pg)
    return raw, paras, pages


def _norm(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


_COG = [(r"ph", "f"), (r"th", "t"), (r"y", "i"), (r"ll", "l"), (r"qu", "k"), (r"c(?=[ei])", "s"), (r"z", "s"), (r"ck", "k"),
        (r"(cion|tion|sion|zione)$", "sion"), (r"(ismo|ism|isme)$", "ism"), (r"(mente|ment|ly)$", ""), (r"(dad|ty|tät|té)$", "t"),
        (r"(a|o|e|as|os|es|s)$", ""), (r"(.)\1", r"\1")]


def cog(word):
    """Crude cognate stem shared by Romance/English/German spellings: philosophy/filosofía → filosof."""
    w = word
    for pat, rep in _COG: w = re.sub(pat, rep, w)
    return w[:6]


def feats(s):
    s = re.sub(r"\[\d+\]", "", s); low = _norm(s)
    nums = set(re.findall(r"\b\d{2,4}\b", s))
    names = {_norm(m.group(1))[:5] for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-ZÁÉÍÓÚÑÄÖÜ][a-záéíóúñüäöß]{3,})", s)}
    stems = {cog(w) for w in re.findall(r"[a-z]{6,}", low)}
    caps = len(s) < 120 and s == s.upper() and sum(c.isalpha() for c in s) >= 3
    return nums, names, stems, len(s), caps


def sim(fo, ft):
    lr = min(fo[3], ft[3]) / max(fo[3], ft[3], 1)
    nj = len(fo[1] & ft[1]) / len(fo[1] | ft[1]) if (fo[1] | ft[1]) else 0.5
    sj = len(fo[2] & ft[2]) / len(fo[2] | ft[2]) if (fo[2] | ft[2]) else 0.5
    dj = len(fo[0] & ft[0]) / len(fo[0] | ft[0]) if (fo[0] | ft[0]) else 0.5
    v = 0.3 * lr + 0.25 * nj + 0.35 * min(1.0, sj * 2.5) + 0.1 * dj
    if fo[4] != ft[4]: v -= 0.35                                   # a heading against a body paragraph
    return v


def merge(fs): return (set().union(*[f[0] for f in fs]), set().union(*[f[1] for f in fs]), set().union(*[f[2] for f in fs]), sum(f[3] for f in fs), all(f[4] for f in fs))


def align(O, T, band=80):
    Fo, Ft = [feats(x) for x in O], [feats(x) for x in T]
    n, m = len(O), len(T); NEG = -1e18; GAP = -0.15
    D = {}; B = {}; D[(0, 0)] = 0.0
    def upd(key, val, mv):
        if val > D.get(key, NEG): D[key] = val; B[key] = mv
    for i in range(n + 1):
        c = round(i * m / max(n, 1)); lo, hi = max(0, c - band), min(m, c + band)
        for j in range(lo, hi + 1):
            cur = D.get((i, j))
            if cur is None: continue
            if i < n: upd((i + 1, j), cur + GAP, (1, 0))
            if j < m: upd((i, j + 1), cur + GAP, (0, 1))
            if i < n and j < m: upd((i + 1, j + 1), cur + sim(Fo[i], Ft[j]), (1, 1))
            for a in (2, 3, 4, 5, 6):
                if i + a <= n and j < m:
                    v = sim(merge(Fo[i:i + a]), Ft[j]); mix = len({f[4] for f in Fo[i:i + a]}) > 1
                    upd((i + a, j + 1), cur + v + (a - 1) * (v - 0.75) - (0.6 if mix else 0), (a, 1))
            for b in (2, 3):
                if i < n and j + b <= m:
                    v = sim(Fo[i], merge(Ft[j:j + b])); mix = len({f[4] for f in Ft[j:j + b]}) > 1
                    upd((i + 1, j + b), cur + v + (b - 1) * (v - 0.75) - (0.6 if mix else 0), (1, b))
    if (n, m) not in B and (n, m) != (0, 0): sys.exit("alignment failed: increase --band")
    i, j = n, m; steps = []
    while (i, j) != (0, 0):
        a, b = B[(i, j)]; steps.append((i - a, i, j - b, j)); i -= a; j -= b
    return steps[::-1]


def locate_all(raw: str, paras):
    """Sequential (start, end) of each normalised paragraph in the raw file (None where it cannot be found)."""
    out = []; cur = 0
    for para in paras:
        core = re.sub(r"^\(\d{1,3}\)\s+", "", para)          # a (n) note: the raw may say [^n]:
        span = None
        k = raw.find(core, cur)
        if k >= 0: span = (k, k + len(core))
        else:
            head, tail = core[:30], core[-30:]; hs = raw.find(head, cur)
            if hs >= 0:
                te = raw.find(tail, hs)
                if te >= 0 and te - hs <= len(core) * 2 + 40: span = (hs, te + len(tail))
        if span: cur = span[1]
        out.append(span)
    return out


def is_caps(s): return len(s) < 120 and s == s.upper() and sum(c.isalpha() for c in s) >= 3


def is_fragment_boundary(a: str, b: str):
    """Does paragraph b look like the OCR-cut continuation of a? (never across a heading/body boundary)"""
    if is_caps(a) != is_caps(b): return False
    bb = re.sub(r"^\[\d{1,4}\]\s*", "", b)
    return (re.search(r"\w-$", a) is not None) or (not TERMINAL.search(a)) or bb[:1].islower() or len(a) < 40 or len(bb) < 40


def junk_tail(s: str):
    """A short lowercase fragment ('osas.', 'as pr pa') — the cut-off tail of a paragraph; needs the scan."""
    core = re.sub(r"^\[\d{1,4}\]\s*", "", s)
    return len(core) <= 14 and core == core.lower() and sum(c.isalpha() for c in core) >= 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("orig"); ap.add_argument("trans"); ap.add_argument("--emit", metavar="DIR"); ap.add_argument("--show", type=int, default=40); ap.add_argument("--band", type=int, default=80)
    a = ap.parse_args(); op, tp = pathlib.Path(a.orig).expanduser(), pathlib.Path(a.trans).expanduser()
    raw_o, O, PO = load(op, "orig"); raw_t, T, PT = load(tp, "trans")
    LO, LT = locate_all(raw_o, O), locate_all(raw_t, T)
    Fo, Ft = [feats(x) for x in O], [feats(x) for x in T]
    steps = align(O, T, a.band)
    rows, missing, fx_o, fx_t, manual, issues = [], [], [], [], 0, []
    last_t_for_o = {}
    for oi, oe, ti, te in steps:
        for k in range(oi, oe): last_t_for_o[k] = ti if te > ti else None
    def anchor_for(oi):
        for k in range(oi - 1, -1, -1):
            t = last_t_for_o.get(k)
            if t is not None: return T[t][:80]
        return None
    for oi, oe, ti, te in steps:
        ko, kt = oe - oi, te - ti; ol = sum(len(O[k]) for k in range(oi, oe)); tl = sum(len(T[k]) for k in range(ti, te))
        ratio = tl / ol if ol else None; hint = ""; kind = f"{ko}:{kt}"
        if ko == 1 and kt == 1:
            if ratio and ol > 200 and (ratio < 0.55 or ratio > 1.8): hint = f"length ratio {ratio:.2f} — one side lost or gained text; compare"
        elif kt == 0:
            if junk_tail(O[oi]):
                hint = f"OCR cut-off tail {O[oi]!r} on p.{PO[oi]} — the end of a paragraph the OCR broke off: read the scan page and repair by hand"; manual += 1; issues.append({"i": oi, "page": PO[oi], "orig": O[oi], "why": "cut-off tail"})
            elif is_caps(O[oi]) and len(O[oi]) < 40 and oi < 4:
                hint = "front-matter line with no counterpart — repair the OCR (half-title, series line) or delete it"; manual += 1; issues.append({"i": oi, "page": PO[oi], "orig": O[oi], "why": "front matter"})
            elif re.match(r"^\(\d{1,3}\)\s", O[oi]):
                hint = "a (n) note with no counterpart → missing.json — but first check the scan: OCR sometimes turns a page's last line into a note"
                missing.append({"i": oi, "page": PO[oi], "orig": O[oi], "after_trans": anchor_for(oi), "trans": "", "note": "verify on the scan that this note exists"})
            else:
                hint = "MISSING in translation → missing.json"; missing.append({"i": oi, "page": PO[oi], "orig": O[oi], "after_trans": anchor_for(oi), "trans": ""})
        elif ko == 0:
            hint = "EXTRA in translation (duplicate / LLM addition?) — delete or check"
        elif kt == 1:
            part_sims = [sim(Fo[k], Ft[ti]) for k in range(oi, oe)]; best = oi + part_sims.index(max(part_sims))
            tails = [k for k in range(oi, oe) if junk_tail(O[k])]
            frag = all(is_fragment_boundary(O[k], O[k + 1]) for k in range(oi, oe - 1))
            loc = [LO[k] for k in range(oi, oe)]
            notes = [k for k in range(oi, oe) if re.match(r"^\(\d{1,3}\)\s", O[k])]
            if notes and best not in notes:
                for k in notes: missing.append({"i": k, "page": PO[k], "orig": O[k], "after_trans": (T[ti][:80] if k > best else anchor_for(oi)), "trans": "", "note": "verify on the scan that this note exists — OCR sometimes turns a page's last line into a note"})
                hint = f"(n) note {[O[k][:30] for k in notes]} with no counterpart → missing.json; check the scan p.{PO[notes[0]]} first (a page's last line taken for a note?)"
            elif tails:
                hint = f"OCR cut-off tail {[O[k] for k in tails]} on p.{PO[tails[0]]} — read the scan page (scan_page.py) and repair the paragraph by hand"; manual += 1
            elif max(part_sims) > 0.55 and 0.7 <= tl / max(len(O[best]), 1) <= 1.35 and not frag:
                for k in range(oi, oe):
                    if k == best: continue
                    note = bool(re.match(r"^\(\d{1,3}\)\s", O[k]))
                    missing.append({"i": k, "page": PO[k], "orig": O[k], "after_trans": (T[ti][:80] if k > best else anchor_for(oi)), "trans": "",
                                    "note": "a note the OCR may have invented from a page's last line — check the scan before translating" if note else ""})
                hint = f"translation matches O{best} alone → {ko - 1} paragraph(s) MISSING → missing.json" + (" (a (n) note: verify on the scan that it exists)" if any(re.match(r"^\(\d{1,3}\)\s", O[k]) for k in range(oi, oe) if k != best) else "")
            elif frag and all(loc) and all(loc[k + 1][0] > loc[k][1] for k in range(len(loc) - 1)):
                old = raw_o[loc[0][0]:loc[-1][1]]; parts = [raw_o[s:e].strip() for s, e in loc]; new = parts[0]
                for nxt in parts[1:]:
                    mk = re.match(r"^(\[\d{1,4}\])\s+(.*)$", nxt, re.S); body = mk.group(2) if mk else nxt
                    if re.search(r"\w-$", new) and body[:1].islower():
                        w = re.search(r"(\w+)-$", new).group(1); new = new[: -len(w) - 1] + ((mk.group(1) + " ") if mk else "") + w + body
                    else: new = new + " " + nxt
                if raw_o.count(old) == 1: fx_o.append([old, new]); hint = f"OCR split into {ko} → auto-merge proposed (fixes_orig.json)"
                else: hint = "OCR split — merge by hand"; manual += 1
            else:
                hint = f"translation merged {ko} source paragraphs — split the translation, or merge the source if the print has one paragraph; boundaries: …{O[oi][-40:]!r} | {O[oi+1][:40]!r}"; manual += 1
        else:  # 1:k
            loc = [LT[k] for k in range(ti, te)]
            if all(loc) and all(loc[k + 1][0] > loc[k][1] for k in range(len(loc) - 1)):
                old = raw_t[loc[0][0]:loc[-1][1]]; new = " ".join(raw_t[s:e].strip() for s, e in loc)
                if raw_t.count(old) == 1: fx_t.append([old, new]); hint = f"translator split into {kt} → auto-merge proposed (fixes_trans.json)"
                else: hint = "translator split — merge by hand"; manual += 1
            else: hint = "translator split — merge by hand (could not locate in the raw file)"; manual += 1
        rows.append({"kind": kind, "o": [oi, oe], "t": [ti, te], "page": PO[oi] if oe > oi else None, "olen": ol, "tlen": tl, "ratio": round(ratio, 2) if ratio else None, "hint": hint})
    bad = [r for r in rows if r["hint"]]
    print(f"  {op.name}: {len(O)} paragraphs | {tp.name}: {len(T)} paragraphs | rows: {len(rows)}, one-to-one: {sum(1 for r in rows if r['kind']=='1:1')}, to fix: {len(bad)}")
    print(f"  missing in translation: {len(missing)} | auto-fixes: {len(fx_o)} source merges, {len(fx_t)} translation merges | by hand: {manual}")
    for r in bad[: a.show]:
        oi, oe = r["o"]; ti, te = r["t"]
        print(f"\n  {r['kind']:4s} o[{oi}:{oe}] t[{ti}:{te}] p.{r['page']}  {r['olen']}|{r['tlen']}  {r['hint']}")
        for k in range(oi, oe): print(f"     O{k}: {O[k][:80]!r}" + (f" … {O[k][-30:]!r}" if len(O[k]) > 110 and r['kind'] != '1:1' else ""))
        for k in range(ti, te): print(f"     T{k}: {T[k][:80]!r}" + (f" … {T[k][-30:]!r}" if len(T[k]) > 110 and r['kind'] != '1:1' else ""))
    if len(bad) > a.show: print(f"\n  … {len(bad) - a.show} more rows in alignment.json")
    if a.emit:
        d = pathlib.Path(a.emit).expanduser(); d.mkdir(parents=True, exist_ok=True)
        (d / "alignment.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "missing.json").write_text(json.dumps(missing, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "source_issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "fixes_orig.json").write_text(json.dumps(fx_o, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "fixes_trans.json").write_text(json.dumps(fx_t, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  → {d}/alignment.json, missing.json ({len(missing)}), fixes_orig.json ({len(fx_o)}), fixes_trans.json ({len(fx_t)})")
        if fx_o or fx_t or missing:
            print("  next: " + "; ".join(x for x in [
                f"python3 fix_orig.py {op} < {d}/fixes_orig.json" if fx_o else "",
                f"python3 fix_orig.py {tp} < {d}/fixes_trans.json" if fx_t else "",
                f"fill 'trans' in {d}/missing.json, then python3 apply_missing.py {tp} {d}/missing.json" if missing else ""] if x))
    sys.exit(0 if not bad else 1)


if __name__ == "__main__": main()
