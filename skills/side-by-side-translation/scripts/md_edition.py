#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_edition.py — two Markdown files in, the parallel edition out (PDF + HTML), in one command.

    python3 md_edition.py ORIG.refined.md TRANS.refined.md --author "Jorge Guillermo Llosa" \\
        --work "<i>La filosofía humanista de Mariano Iberico</i> (1952)" --lang es en \\
        --footnote "…" -o ~/Desktop/Title.pdf [--html ~/Desktop/Title.html | --no-html] [--preview 2]

Steps (each printed; the run stops at the first that fails):
  1. align_check.py — every paragraph one-to-one? If not, its report is printed and the run exits 2:
     apply fixes_*.json, fill missing.json → apply_missing.py, repair what it flags, run again.
  2. build_pdf.py    — front matter kept out of the contents, run-in titles at level 3, previews.
  3. side_by_side_html.py — the reader with the sidebar TOC, same front-matter rule, run-in titles nested.
Any further build_pdf.py flag can be given after `--`, e.g. `-- --facing --trim 6x9 --level arabic=3`.
Both deliverables land next to each other (default ~/Desktop/<slug of --work>.pdf/.html)."""
from __future__ import annotations
import argparse, html, pathlib, re, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
PY = sys.executable


def run(args, tail=None):
    show = [pathlib.Path(x).name if ("/" in x and not x.startswith("<")) else (x if " " not in x else repr(x)) for x in args[1:]]
    print("\n$ " + " ".join(show))
    r = subprocess.run(args, text=True, capture_output=True)
    out = (r.stdout + r.stderr).rstrip("\n")
    if tail and r.returncode == 0: out = "\n".join(out.split("\n")[-tail:])
    print(out); return r.returncode


def main():
    argv = sys.argv[1:]; extra = []
    if "--" in argv: k = argv.index("--"); argv, extra = argv[:k], argv[k + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("orig"); ap.add_argument("trans")
    ap.add_argument("--author", required=True); ap.add_argument("--work", required=True, help="HTML allowed: \"<i>Title</i> (1952)\"")
    ap.add_argument("--lang", nargs=2, required=True, metavar=("LEFT", "RIGHT"))
    ap.add_argument("--edition", default=""); ap.add_argument("--footnote", action="append", default=[]); ap.add_argument("--credit", default=""); ap.add_argument("--running-head", default="")
    ap.add_argument("-o", "--output"); ap.add_argument("--html"); ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--title", help="HTML title (default: --work without tags)"); ap.add_argument("--left-label"); ap.add_argument("--right-label")
    ap.add_argument("--toc-chapters", choices=["roman", "arabic"], default="roman"); ap.add_argument("--runin-level", type=int, default=3)
    ap.add_argument("--preview", type=int, default=2); ap.add_argument("--check-dir", default=None, help="where align_check writes its JSON (default: next to the PDF, <slug>_check/)")
    ap.add_argument("--check-only", action="store_true"); ap.add_argument("--skip-check", action="store_true")
    a = ap.parse_args()
    orig, trans = pathlib.Path(a.orig).expanduser().resolve(), pathlib.Path(a.trans).expanduser().resolve()
    work_plain = html.unescape(re.sub(r"<[^>]+>", "", a.work)); slug = re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", work_plain)).strip("-")[:80] or "edition"
    pdf = pathlib.Path(a.output).expanduser() if a.output else pathlib.Path.home() / "Desktop" / f"{slug}.pdf"
    htm = pathlib.Path(a.html).expanduser() if a.html else pdf.with_suffix(".html")
    chk = pathlib.Path(a.check_dir).expanduser() if a.check_dir else pdf.with_name(pdf.stem + "_check"); chk.mkdir(parents=True, exist_ok=True)
    if not a.skip_check:
        rc = run([PY, str(HERE / "align_check.py"), str(orig), str(trans), "--emit", str(chk)])
        if rc != 0:
            print(f"\n  ✗ not one-to-one yet — apply {chk}/fixes_*.json with fix_orig.py, fill {chk}/missing.json and run apply_missing.py, repair the flagged spots, then run md_edition.py again."); sys.exit(2)
        if a.check_only: print("\n  ✓ aligned; --check-only, stopping."); return
    front = ["--author", a.author, "--work", a.work, "--lang", *a.lang]
    if a.edition: front += ["--edition", a.edition]
    for f in a.footnote: front += ["--footnote", f]
    if a.credit: front += ["--credit", a.credit]
    if a.running_head: front += ["--running-head", a.running_head]
    rc = run([PY, str(HERE / "build_pdf.py"), str(orig), str(trans), *front, "--toc-chapters", a.toc_chapters, "--level", f"runin={a.runin_level}", "--front-matter", "auto", "--preview", str(a.preview), "-o", str(pdf), *extra], tail=8)
    if rc != 0: sys.exit(rc)
    if not a.no_html:
        title = a.title or work_plain
        args = [PY, str(HERE / "side_by_side_html.py"), str(orig), str(trans), "--artifact", "--toc", "--toc-chapters", a.toc_chapters, "--marginal-level", f"tc{min(a.runin_level, 3) - 1}", "--front-matter", "auto",
                "--title", title, "--lang", *a.lang, "-o", str(chk / "reader.fragment.html"), "--html-copy", str(htm)]
        if a.left_label: args += ["--left-label", a.left_label]
        if a.right_label: args += ["--right-label", a.right_label]
        rc = run(args, tail=4)
        if rc != 0: sys.exit(rc)
    prev = pdf.with_name(pdf.stem + "_preview")
    if a.preview:
        try:
            import shutil
            if shutil.which("pdfinfo") and shutil.which("pdftoppm"):
                n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], text=True, capture_output=True).stdout).group(1))
                mid = max(2, n // 2); prev.mkdir(exist_ok=True)
                subprocess.run(["pdftoppm", "-png", "-r", "80", "-f", str(mid), "-l", str(mid), "-singlefile", str(pdf), str(prev / f"page-mid-{mid}")], check=True)
        except Exception as e: print(f"  (middle-page preview skipped: {e})")
    print(f"\n  ✓ {pdf}" + ("" if a.no_html else f"\n  ✓ {htm}  (artifact fragment: {chk / 'reader.fragment.html'})") + (f"\n  previews: {prev}/page-*.png — read page 1 and one middle page, then delete the folder" if a.preview else ""))


if __name__ == "__main__": main()
