#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chunk_tools.py — book-length translation by parallel sub-agents, alignment guaranteed.

    python3 chunk_tools.py split  SRC.md DIR --words 12000 --source fr --target en [--glossary g.txt]
    python3 chunk_tools.py verify DIR/chNN            # checks chNN.trans.md against chNN.src.md (exit 1 on problems)
    python3 chunk_tools.py status DIR                 # which chunks are done / clean / missing
    python3 chunk_tools.py assemble DIR -o TRANS.md   # all clean chunks → one translation file, tags removed

`split` writes DIR/chNN.src.md (paragraphs tagged [[i]], blank-line separated, never cutting a heading
from its paragraph) and DIR/BRIEF.md (rules + glossary). A sub-agent reads the brief and one src file,
writes chNN.trans.md with the same tags, runs `verify` until clean, and reports. The checks are the same
as translate_md.py's: every tag once and in order, note numbers, numbering and capitals of headings, and
the [n] page markers (a marker the translator dropped is re-inserted at the proportional word)."""
from __future__ import annotations
import argparse, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from translate_md import load_paragraphs, is_caps, anchors, parse_reply, check_chunk, repair_markers, LANG, TAG

BRIEF = """# Translator's brief — {src} → {tgt}

You are translating one chunk of a scholarly parallel-text edition. The chunk file lists paragraphs, each
starting with a tag like `[[12]]`. Write your translation to the output file named in your instructions,
in exactly the same shape: every paragraph, in order, starting with its own tag, one blank line between
paragraphs, nothing else (no preamble, no notes of your own, no code fences).

Mandatory:
1. Never merge, split, drop or add paragraphs. One tag in → one tag out.
2. Page markers such as `[23]` stay, placed at the word where the page turns in your sentence.
3. A paragraph beginning `(1)` is a footnote: keep the `(1)`. A cue such as `mot(1)` inside a sentence stays
   `word(1)`. Numbering at the start of a heading (`I.`, `1°`, `3.`) stays. A heading set in CAPITALS is
   returned in CAPITALS; a heading in sentence case in sentence case.
4. Faithful and complete, in flowing {tgt} of a scholarly register; keep the author's sentence structure
   where {tgt} allows; keep Latin and Greek phrases as they are (add the {tgt} in brackets once if useful);
   keep book and article titles in their original language.
5. Run the check named in your instructions before you report; fix what it lists.
6. Renderings you are unsure about (at most three): append them as one line each to the file `flags.md` in the
   chunk folder (`chNN: word — chosen rendering — alternative`), so the reviser finds them later.
{glossary}"""

PROMPT = """Translate one chunk of {work} ({src} → {tgt}) for a parallel-text edition. Work in as few turns as possible:
TURN 1: Read {brief} and {srcf} (two Read calls in the same turn).
TURN 2: Write {trf} — every paragraph, same order, each starting with its own [[i]] tag, blank line between, nothing else. Keep [n] page markers at the word where the page turns, (n) note numbers and cues, heading numbering; CAPITALS stay CAPITALS.{twostep}
TURN 3: Run `python3 "{tools}" verify {prefix}`; fix only what it lists (small Python replacements, never the Edit tool), run it again until ✓.
Then append at most three doubtful renderings to {flags} (one line each: {name}: word — rendering — alternative) and reply in ONE line: "{name} done, N paragraphs, verify ✓"."""


def split(a):
    src = pathlib.Path(a.src).expanduser(); d = pathlib.Path(a.dir).expanduser(); d.mkdir(parents=True, exist_ok=True)
    items = load_paragraphs(src); paras = [(i, t) for i, (t, pb) in enumerate(items) if not pb]
    chunks = []; cur = []; words = 0
    for k, (i, t) in enumerate(paras):
        cur.append((i, t)); words += len(t.split())
        nxt_is_body = k + 1 < len(paras) and not is_caps(paras[k + 1][1]) and not re.match(r"^(?:[IVX]+\.|\d{1,2}[.°])\s", paras[k + 1][1])
        if words >= a.words and not is_caps(t) and not re.match(r"^(?:[IVX]+\.|\d{1,2}[.°])\s\S.{0,120}$", t) and nxt_is_body:
            chunks.append(cur); cur = []; words = 0
    if cur: chunks.append(cur)
    gl = ""
    if a.glossary: gl = "\nGlossary — use these renderings consistently:\n" + pathlib.Path(a.glossary).expanduser().read_text(encoding="utf-8").strip() + "\n"
    (d / "BRIEF.md").write_text(BRIEF.format(src=LANG.get(a.source, a.source), tgt=LANG.get(a.target, a.target), glossary=gl), encoding="utf-8")
    (d / "layout.json").write_text(json.dumps({"source": str(src), "items": [(t, pb) for t, pb in items], "chunks": [[i for i, _ in c] for c in chunks]}, ensure_ascii=False), encoding="utf-8")
    prompts = []
    for n, c in enumerate(chunks, 1):
        (d / f"ch{n:02d}.src.md").write_text("\n\n".join(f"[[{i}]] {t}" for i, t in c) + "\n", encoding="utf-8")
        w = sum(len(t.split()) for _, t in c); name = f"ch{n:02d}"
        twostep = (" The chunk is long: write the first half of the paragraphs with the Write tool, then append the rest with ONE Python heredoc (utf-8), so no single output exceeds ~6,000 words." if w > 6500 else "")
        prompts.append(f"### {name}\n" + PROMPT.format(work=a.work or src.stem, src=LANG.get(a.source, a.source), tgt=LANG.get(a.target, a.target), brief=d / "BRIEF.md", srcf=d / f"{name}.src.md", trf=d / f"{name}.trans.md",
                                                       twostep=twostep, tools=pathlib.Path(__file__).resolve(), prefix=d / name, flags=d / "flags.md", name=name))
    (d / "prompts.md").write_text("\n\n".join(prompts) + "\n", encoding="utf-8"); (d / "flags.md").write_text("", encoding="utf-8")
    print(f"  {len(paras)} paragraphs → {len(chunks)} chunks in {d} (one ready prompt per chunk in prompts.md; translators' doubts collect in flags.md):")
    for n, c in enumerate(chunks, 1): print(f"    ch{n:02d}: paragraphs {c[0][0]}–{c[-1][0]}, {sum(len(t.split()) for _, t in c)} words, first: {c[0][1][:60]!r}")


def load_tagged(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    parts = TAG.split(text); ids = [int(x) for x in parts[1::2]]; texts = [t.strip() for t in parts[2::2]]
    return ids, texts


def verify_one(prefix):
    prefix = pathlib.Path(prefix); srcf = prefix.with_name(prefix.name + ".src.md"); trf = prefix.with_name(prefix.name + ".trans.md")
    if not trf.exists(): print(f"  {prefix.name}: no translation file yet"); return 2
    sids, stexts = load_tagged(srcf); src_map = dict(zip(sids, stexts))
    got, why = parse_reply(trf.read_text(encoding="utf-8"), sids)
    if got is None:
        tids, _ = load_tagged(trf); missing = [i for i in sids if i not in tids]; extra = [i for i in tids if i not in sids]; dup = [i for i in set(tids) if tids.count(i) > 1]
        print(f"  {prefix.name}: tags do not match — missing {missing[:10]}, extra {extra[:10]}, duplicated {dup[:10]}, order/other: {why}"); return 1
    bad = check_chunk(src_map, got); fixed = 0
    for i, w in list(bad):
        if w.startswith("markers"): got[i] = repair_markers(src_map[i], got[i]); fixed += 1
    bad = [(i, w) for i, w in bad if not w.startswith("markers")]
    unt = [i for i, t in got.items() if "⟪UNTRANSLATED⟫" in t or t.strip() == src_map[i].strip() and len(t) > 40]
    if fixed: trf.write_text("\n\n".join(f"[[{i}]] {got[i]}" for i in sids) + "\n", encoding="utf-8")
    if bad or unt:
        for i, w in bad[:12]: print(f"  {prefix.name} [[{i}]]: {w} — source starts {src_map[i][:50]!r}, yours starts {got[i][:50]!r}")
        for i in unt[:6]: print(f"  {prefix.name} [[{i}]]: looks untranslated")
        print(f"  {prefix.name}: {len(bad) + len(unt)} problem(s)"); return 1
    print(f"  {prefix.name}: ✓ {len(sids)} paragraphs" + (f" ({fixed} page markers re-placed)" if fixed else "")); return 0


def status(a):
    d = pathlib.Path(a.dir).expanduser(); rc = 0
    for f in sorted(d.glob("ch*.src.md")):
        r = verify_one(f.with_name(f.name[:-7])); rc = rc or r
    return rc


def assemble(a):
    d = pathlib.Path(a.dir).expanduser(); lay = json.load(open(d / "layout.json", encoding="utf-8")); out = {}
    for n, ids in enumerate(lay["chunks"], 1):
        trf = d / f"ch{n:02d}.trans.md"
        if not trf.exists(): sys.exit(f"  ch{n:02d}.trans.md missing")
        tids, texts = load_tagged(trf)
        if tids != ids: sys.exit(f"  ch{n:02d}: tags differ from the layout — run verify first")
        out.update(zip(tids, texts))
    lines = []
    for i, (t, pb) in enumerate(lay["items"]): lines.append(t if pb else re.sub(r"\s*\n\s*", " ", out[i]).strip())   # one paragraph = one block, whatever line breaks the translator typed
    o = pathlib.Path(a.output).expanduser(); o.write_text("\n\n".join(lines) + "\n", encoding="utf-8"); print(f"  → {o} ({len(out)} paragraphs)")


def sample(a):
    """A compact bilingual sample (N pairs per chunk, mid-length, evenly spaced) for ONE critic agent instead of
    re-reading the whole book: false friends, drifted glossary terms, dropped clauses show up in 40 pairs."""
    d = pathlib.Path(a.dir).expanduser(); lay = json.load(open(d / "layout.json", encoding="utf-8")); out = []
    for n, ids in enumerate(lay["chunks"], 1):
        trf = d / f"ch{n:02d}.trans.md"
        if not trf.exists(): continue
        sids, stexts = load_tagged(d / f"ch{n:02d}.src.md"); tids, ttexts = load_tagged(trf); tmap = dict(zip(tids, ttexts))
        cand = [(i, t) for i, t in zip(sids, stexts) if 300 <= len(t) <= 900 and i in tmap]
        step = max(1, len(cand) // max(a.n, 1))
        for i, t in cand[::step][: a.n]: out.append(f"## ch{n:02d} [[{i}]]\n\nSOURCE: {t}\n\nTRANSLATION: {tmap[i]}")
    o = pathlib.Path(a.output).expanduser(); o.write_text("\n\n".join(out) + "\n", encoding="utf-8"); print(f"  → {o} ({len(out)} pairs, {sum(len(x.split()) for x in out)} words)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split"); s.add_argument("src"); s.add_argument("dir"); s.add_argument("--words", type=int, default=9000, help="words per chunk (default 9000: measured sweet spot — fewer agents cost less, but a single write past ~12k words stalls)"); s.add_argument("--source", required=True); s.add_argument("--target", required=True); s.add_argument("--glossary"); s.add_argument("--work", help="author, title (year) for the prompts")
    sm = sub.add_parser("sample", help="bilingual sample for one critic agent: N mid-length pairs per chunk"); sm.add_argument("dir"); sm.add_argument("-n", type=int, default=3); sm.add_argument("-o", "--output", required=True)
    v = sub.add_parser("verify"); v.add_argument("prefix")
    st = sub.add_parser("status"); st.add_argument("dir")
    asm = sub.add_parser("assemble"); asm.add_argument("dir"); asm.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    if a.cmd == "split": split(a)
    elif a.cmd == "sample": sample(a)
    elif a.cmd == "verify": sys.exit(verify_one(a.prefix))
    elif a.cmd == "status": sys.exit(status(a))
    else: assemble(a)


if __name__ == "__main__": main()
