#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_page.py — one book page of the scan as a PNG you can Read, in one call.

    python3 scan_page.py SRC N [N …] [-o DIR] [--width 1400] [--offset K]

SRC is a folder of page images (page-NN.tif/.png/.jpg, e.g. ScanTailor's `out/`) or a PDF.
N is the book page printed in the [n] markers; --offset K when PDF page = book page + K.
Prints the PNG paths; read them with the Read tool (≈1.5k tokens each — only the pages a
report flagged)."""
import argparse, pathlib, re, subprocess, sys, shutil
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("pages", nargs="+", type=int)
ap.add_argument("-o", "--out", default=None); ap.add_argument("--width", type=int, default=1400); ap.add_argument("--offset", type=int, default=0)
a = ap.parse_args(); src = pathlib.Path(a.src).expanduser(); out = pathlib.Path(a.out or ".").expanduser(); out.mkdir(parents=True, exist_ok=True)
for n in a.pages:
    dst = out / f"scan-p{n}.png"
    if src.is_dir():
        cands = [p for p in src.iterdir() if re.fullmatch(rf"(?:page[-_])?0*{n}\.(?:tif|tiff|png|jpe?g)", p.name, re.I)]
        if not cands: sys.exit(f"no page image for {n} in {src}")
        subprocess.run(["sips", "-s", "format", "png", "-Z", str(a.width), str(cands[0]), "--out", str(dst)], check=True, capture_output=True)
    else:
        if not shutil.which("pdftoppm"): sys.exit("pdftoppm (poppler) needed for PDF sources")
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", str(n + a.offset), "-l", str(n + a.offset), "-singlefile", "-scale-to", str(a.width), str(src), str(dst.with_suffix(""))], check=True)
    print(dst)
