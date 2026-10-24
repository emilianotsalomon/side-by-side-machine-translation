#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""book_run.py — run one book, or a queue of books, from scan/OCR to the parallel edition, unattended.

    python3 book_run.py BOOKDIR [BOOKDIR …] [--until STAGE] [--force STAGE[,STAGE]] [--jobs 2]
    python3 book_run.py --init BOOKDIR        # write a meta.json template to fill in

A book is a folder with `meta.json`:
{
  "author": "Jorge Guillermo Llosa", "work": "<i>La filosofía humanista de Mariano Iberico</i> (1952)",
  "lang": ["es", "en"], "edition": "the Bogotá edition of 1952",   // or "footnote": "…" (HTML)
  "scan": "book.pdf" | "straightened/out",                            // optional if ocr is given
  "ocr": "book.ocr.md", "trans": "book.trans.md",                     // paths relative to the folder; created if missing
  "glossary": "glossary.txt", "provider": "lmstudio", "model": null,  // for translate_md.py
  "left_label": "Español · 1952", "right_label": "English translation", "build_args": ["--facing", "--trim", "6x9"]
}
Stages, each skipped when its output exists (use --force to redo): ocr → clean → translate → check → build.
`check` runs align_check.py; when it is not one-to-one the book STOPS with the report in `STATUS.md` and
`check/` (fixes_*.json, missing.json) for a person or an agent to settle; run again afterwards. `build`
runs md_edition.py (PDF + HTML + previews into `out/`). The queue prints one line per book at the end."""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
HERE = pathlib.Path(__file__).resolve().parent; PY = sys.executable
STAGES = ["ocr", "clean", "translate", "check", "build"]
TEMPLATE = {"author": "", "work": "<i>Title</i> (YEAR)", "lang": ["es", "en"], "edition": "the first edition of YEAR", "footnote": "",
            "scan": "", "ocr": "book.ocr.md", "trans": "book.trans.md", "glossary": "", "provider": "lmstudio", "model": None,
            "left_label": "", "right_label": "", "build_args": []}


def sh(args, log, cwd=None):
    log.write("\n$ " + " ".join(str(x) for x in args) + "\n"); log.flush()
    r = subprocess.run([str(x) for x in args], text=True, capture_output=True, cwd=cwd)
    log.write(r.stdout + r.stderr); log.flush(); return r.returncode, r.stdout + r.stderr


def refined(p: pathlib.Path): return p.with_name(p.name[:-3] + ".refined.md") if p.name.endswith(".md") else p.with_name(p.stem + ".refined" + p.suffix)


def run_book(d: pathlib.Path, until: str, force: set):
    meta = json.load(open(d / "meta.json", encoding="utf-8")); t0 = time.time()
    log = open(d / "run.log", "a", encoding="utf-8"); log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M')} =====\n")
    ocr = d / meta.get("ocr", "book.ocr.md"); trans = d / meta.get("trans", "book.trans.md"); out = d / "out"; chk = d / "check"
    status = []
    def stop(msg):
        (d / "STATUS.md").write_text(f"# {d.name}\n\n{msg}\n", encoding="utf-8"); log.close()
        state = next((l.strip() for l in msg.splitlines() if l.startswith(("STOPPED", "DONE"))), msg.splitlines()[-1].strip() if msg.strip() else "")
        return (d.name, state, time.time() - t0)
    # 1. ocr
    if "ocr" in force or not ocr.exists():
        scan = meta.get("scan")
        if not scan: return stop(f"STOPPED at ocr: no `{ocr.name}` and no `scan` in meta.json")
        rc, o = sh(["ocr", d / scan, "--out", ocr], log)
        if rc or not ocr.exists(): return stop(f"STOPPED at ocr (exit {rc}):\n```\n{o[-1500:]}\n```")
        status.append("ocr ✓")
    if until == "ocr": return stop("\n".join(status))
    # 2. clean
    ro = refined(ocr)
    if "clean" in force or not ro.exists():
        rc, o = sh([PY, HERE / "md_clean.py", ocr, "--json", d / "clean_report.json"], log)
        if rc: return stop(f"STOPPED at clean:\n```\n{o[-1500:]}\n```")
        status.append("clean ✓ " + " | ".join(l.strip() for l in o.splitlines() if l.strip().startswith("[!]")))
    if until == "clean": return stop("\n".join(status))
    # 3. translate (source of the translation is the REFINED ocr)
    if "translate" in force or not trans.exists():
        args = [PY, HERE / "translate_md.py", ro, "--source", meta["lang"][0], "--target", meta["lang"][1], "-o", trans, "--provider", meta.get("provider", "lmstudio"), "--resume"]
        if meta.get("model"): args += ["--model", meta["model"]]
        if meta.get("glossary"): args += ["--glossary", d / meta["glossary"]]
        rc, o = sh(args, log)
        if rc or not trans.exists(): return stop(f"STOPPED at translate (exit {rc}):\n```\n{o[-2000:]}\n```")
        status.append("translate ✓ " + o.strip().splitlines()[-1])
    rt = trans if trans.name.endswith(".refined.md") else refined(trans)
    if "clean" in force or not rt.exists():
        rc, o = sh([PY, HERE / "md_clean.py", trans, "--side", "trans", "-o", rt], log)
        if rc: return stop(f"STOPPED cleaning the translation:\n```\n{o[-1500:]}\n```")
    if until == "translate": return stop("\n".join(status))
    # 4. check
    rc, o = sh([PY, HERE / "align_check.py", ro, rt, "--emit", chk], log)
    if rc:
        return stop("\n".join(status) + f"\n\nSTOPPED at check — not one-to-one. Report:\n```\n{o[-6000:]}\n```\nSettle it: `fix_orig.py {ro.name} < check/fixes_orig.json`, `fix_orig.py {rt.name} < check/fixes_trans.json`, fill check/missing.json → `apply_missing.py {rt.name} check/missing.json`, scan pages for the flagged spots; then run book_run.py again.")
    status.append("check ✓ one-to-one")
    if until == "check": return stop("\n".join(status))
    # 5. build
    out.mkdir(exist_ok=True); slug = d.name
    pdf = out / f"{slug}.pdf"
    if "build" in force or not pdf.exists():
        args = [PY, HERE / "md_edition.py", ro, rt, "--author", meta["author"], "--work", meta["work"], "--lang", *meta["lang"], "-o", pdf, "--check-dir", chk, "--skip-check", "--preview", "1"]
        if meta.get("footnote"): args += ["--footnote", meta["footnote"]]
        elif meta.get("edition"): args += ["--edition", meta["edition"]]
        if meta.get("left_label"): args += ["--left-label", meta["left_label"]]
        if meta.get("right_label"): args += ["--right-label", meta["right_label"]]
        if meta.get("build_args"): args += ["--", *meta["build_args"]]
        rc, o = sh(args, log)
        if rc or not pdf.exists(): return stop("\n".join(status) + f"\n\nSTOPPED at build (exit {rc}):\n```\n{o[-3000:]}\n```")
        pages = next((l.strip() for l in o.splitlines() if l.strip().startswith("layout:")), "")
        status.append(f"build ✓ {pdf.name} ({pages}); previews in out/ — look at page 1 and the middle page")
    return stop("\n".join(status) + f"\n\nDONE — {pdf}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("books", nargs="*"); ap.add_argument("--init", metavar="DIR"); ap.add_argument("--until", choices=STAGES, default="build")
    ap.add_argument("--force", default="", help="comma-separated stages to redo"); ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    if a.init:
        d = pathlib.Path(a.init).expanduser(); d.mkdir(parents=True, exist_ok=True); (d / "meta.json").write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2), encoding="utf-8"); print(f"  wrote {d/'meta.json'} — fill it in"); return
    if not a.books: ap.error("give at least one book folder, or --init DIR")
    force = {s for s in a.force.split(",") if s}
    dirs = [pathlib.Path(b).expanduser().resolve() for b in a.books]
    for d in dirs:
        if not (d / "meta.json").exists(): sys.exit(f"{d}: no meta.json (book_run.py --init {d})")
    if a.jobs > 1:
        with ThreadPoolExecutor(max_workers=a.jobs) as ex: results = list(ex.map(lambda d: run_book(d, a.until, force), dirs))
    else: results = [run_book(d, a.until, force) for d in dirs]
    print("\n  book                            result                                             time")
    for name, msg, secs in results: print(f"  {name[:30]:30s}  {msg[:50]:50s}  {secs:5.0f}s")
    print("\n  details: <book>/STATUS.md and <book>/run.log")
    sys.exit(1 if any(r[1].startswith("STOPPED") for r in results) else 0)


if __name__ == "__main__": main()
