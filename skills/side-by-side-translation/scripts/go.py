#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""go.py — the one-step version: original .md (+ translation .md) in, finished PDF + HTML out.

    sbs go "Book.ocr.md" "Book.trans.md"      # both files
    sbs go "Book.ocr.md"                       # no translation yet: the local model translates it

Asks for author, title, year and languages the first time (saved in meta.json next to the files), then:
cleans both files, translates if needed, checks the alignment, applies every safe fix itself, translates
paragraphs the translation skipped, builds the edition and opens the PDF. Whatever it could not decide is
written in plain words to "TO-DO.txt" next to the files (with the scan pages to look at, when a scan is
found nearby) — fix those lines in the .refined.md files with any text editor and run the same command again.
Options: --provider mock|lmstudio|anthropic (translation backend), --yes (no questions; use meta.json/defaults)."""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys, urllib.request
HERE = pathlib.Path(__file__).resolve().parent; PY = sys.executable
sys.path.insert(0, str(HERE))
from align_check import load, locate_all

LANGS = {"es": "Spanish", "en": "English", "de": "German", "fr": "French", "it": "Italian", "pt": "Portuguese", "la": "Latin"}


def say(msg): print(msg, flush=True)


def run(args, quiet=True):
    r = subprocess.run([str(a) for a in args], text=True, capture_output=True)
    if not quiet: print(r.stdout + r.stderr)
    return r.returncode, r.stdout + r.stderr


def ask(prompt, default=""):
    try: v = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    except EOFError: v = ""
    return v or default


def metadata(folder: pathlib.Path, a):
    mp = folder / "meta.json"; meta = json.load(open(mp, encoding="utf-8")) if mp.exists() else {}
    for k, v in (("author", a.author), ("title", a.title), ("year", a.year)):
        if v: meta[k] = v
    if a.lang: meta["lang"] = list(a.lang)
    need = [k for k in ("author", "title", "year") if not meta.get(k)]
    if need and a.yes: sys.exit("meta.json is missing " + ", ".join(need) + " — add them or run without --yes")
    if need:
        say("\nThree questions for the title page (they are saved for next time):")
        meta["author"] = meta.get("author") or ask("  Author (as it should appear)")
        meta["title"] = meta.get("title") or ask("  Title of the work")
        meta["year"] = meta.get("year") or ask("  Year of the edition")
    if not meta.get("lang"):
        if a.yes: meta["lang"] = ["es", "en"]
        else:
            l1 = ask("  Language of the original (es, de, fr, it, pt, la)", "es"); l2 = ask("  Language of the translation", "en"); meta["lang"] = [l1, l2]
    meta.setdefault("edition", f"the edition of {meta['year']}")
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def refined_name(p: pathlib.Path): return p.with_name(re.sub(r"\.md$", "", p.name) + ".refined.md")


def model_ready(provider):
    if provider != "lmstudio": return True
    try:
        with urllib.request.urlopen("http://localhost:1234/v1/models", timeout=4) as r:
            if json.load(r)["data"]: return True
    except Exception: pass
    lms = pathlib.Path.home() / ".lmstudio/bin/lms"
    if not lms.exists(): say("  LM Studio is not installed — the translation model cannot be started."); return False
    say("  starting LM Studio and loading the translation model (qwen/qwen3.5-9b) …")
    subprocess.run([str(lms), "server", "start"], capture_output=True)
    r = subprocess.run([str(lms), "load", "qwen/qwen3.5-9b", "--yes", "--context-length", "16384"], capture_output=True, text=True)
    return r.returncode == 0


def translate_paragraphs(paras, meta, provider, tmpdir):
    """Translate a list of paragraphs with the same guarantees as the whole-book translation."""
    src = tmpdir / "missing_src.md"; out = tmpdir / "missing_trans.md"
    src.write_text("\n\n".join(paras) + "\n", encoding="utf-8")
    rc, o = run([PY, HERE / "translate_md.py", src, "--source", meta["lang"][0], "--target", meta["lang"][1], "-o", out, "--provider", provider, "--chunk-chars", "4000"])
    if rc or not out.exists(): return None
    got = [b.strip() for b in re.split(r"\n\s*\n", out.read_text(encoding="utf-8")) if b.strip()]
    return got if len(got) == len(paras) else None


def merge_raw(path: pathlib.Path, side, idx_from, idx_to, mode="space"):
    """Merge normalised paragraphs [idx_from, idx_to) in the raw refined file; returns True on success."""
    raw, P, _ = load(path, side); spans = locate_all(raw, P)
    loc = spans[idx_from:idx_to]
    if not all(loc) or any(loc[k + 1][0] <= loc[k][1] for k in range(len(loc) - 1)): return False
    parts = [raw[s:e].strip() for s, e in loc]; new = parts[0]
    for nxt in parts[1:]:
        nxt = re.sub(r"^#+\s+", "", nxt)
        if re.search(r"\w-$", new) and nxt[:1].islower(): new = new[:-1] + nxt
        else: new = new + " " + nxt
    raw = raw[:loc[0][0]] + new + raw[loc[-1][1]:]
    path.write_text(raw, encoding="utf-8"); return True


def delete_raw(path: pathlib.Path, side, idx):
    raw, P, _ = load(path, side); span = locate_all(raw, P)[idx]
    if not span: return False
    s, e = span
    ls = raw.rfind("\n", 0, s) + 1; le = raw.find("\n", e); le = len(raw) if le < 0 else le
    raw = raw[:ls] + raw[le + 1:]
    path.write_text(re.sub(r"\n{3,}", "\n\n", raw), encoding="utf-8"); return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original"); ap.add_argument("translation", nargs="?")
    ap.add_argument("--author"); ap.add_argument("--title"); ap.add_argument("--year"); ap.add_argument("--lang", nargs=2)
    ap.add_argument("--provider", default="lmstudio", choices=["lmstudio", "openai", "anthropic", "mock"]); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out", help="PDF path (default: next to the files, <Title>.pdf)")
    ap.add_argument("--pdf-only", action="store_true", help="skip the HTML reader"); ap.add_argument("--auto-notes", action="store_true", help="translate and insert footnotes the translation lacks without stopping (default: stop and ask, since OCR sometimes invents a note)")
    a = ap.parse_args()
    orig = pathlib.Path(a.original).expanduser().resolve(); folder = orig.parent
    trans = pathlib.Path(a.translation).expanduser().resolve() if a.translation else None
    work = folder / "side-by-side-work"; work.mkdir(exist_ok=True)
    todo = []; verify = []
    meta = metadata(folder, a)

    say("\nStep 1 of 5 — cleaning the OCR text")
    ro = refined_name(orig) if orig.name.endswith(".md") and not orig.name.endswith(".refined.md") else orig
    if not orig.name.endswith(".refined.md"):
        rc, o = run([PY, HERE / "md_clean.py", orig, "-o", ro, "--json", work / "clean_orig.json", "--lang", meta["lang"][0]])
        block = None
        for l in o.splitlines():
            if "[!]" in l:
                block = l.strip()[4:].replace(" — fix or delete it in the .md with fix_orig.py", "").replace(" (fix with fix_orig.py --regex '^## ' '# ')", "").replace(", fix_orig.py", ""); verify.append(block)
            elif block and l.startswith("          "): verify[-1] += "\n      " + l.strip()
            else: block = None
        say(f"  done → {ro.name}")
    if trans is None:
        say("\nStep 2 of 5 — translating (this is the slow part; the model translates paragraph by paragraph)")
        if not model_ready(a.provider): sys.exit("  Could not start the translation model. Open LM Studio, load a model, and run again.")
        trans = folder / (re.sub(r"\.ocr(\.refined)?\.md$", "", orig.name) + ".trans.md")
        rc, o = run([PY, HERE / "translate_md.py", ro, "--source", meta["lang"][0], "--target", meta["lang"][1], "-o", trans, "--provider", a.provider, "--resume"], quiet=False)
        if rc or not trans.exists(): sys.exit("  The translation did not finish. Run the same command again to continue where it stopped.")
    else:
        say("\nStep 2 of 5 — translation supplied, tidying it")
    rt = refined_name(trans) if trans.name.endswith(".md") and not trans.name.endswith(".refined.md") else trans
    if not trans.name.endswith(".refined.md"): run([PY, HERE / "md_clean.py", trans, "--side", "trans", "-o", rt, "--lang", meta["lang"][1]])

    say("\nStep 3 of 5 — lining the two texts up")
    chk = work / "check"; aligned = False
    for round_ in range(4):
        rc, o = run([PY, HERE / "align_check.py", ro, rt, "--emit", chk])
        if rc == 0: aligned = True; break
        fo, ft = json.load(open(chk / "fixes_orig.json", encoding="utf-8")), json.load(open(chk / "fixes_trans.json", encoding="utf-8"))
        if fo: subprocess.run([PY, HERE / "fix_orig.py", ro], input=json.dumps(fo), text=True, capture_output=True); say(f"  joined {len(fo)} paragraph(s) the OCR had split")
        if ft: subprocess.run([PY, HERE / "fix_orig.py", rt], input=json.dumps(ft), text=True, capture_output=True); say(f"  joined {len(ft)} paragraph(s) the translation had split")
        missing = json.load(open(chk / "missing.json", encoding="utf-8"))
        notes_unverified = [m for m in missing if m.get("note")]
        if notes_unverified and not a.auto_notes:
            for m in notes_unverified: todo.append(f"page {m['page']}: the original has a footnote the translation lacks («{m['orig'][:70]}…»). Look at that page of the scan: if the note is real, translate it into check/missing.json and run `sbs missing`; if it is not a note, delete it from the .refined.md file. (Or run with --auto-notes.)")
            missing = [m for m in missing if not m.get("note")]
            if not missing and not (fo or ft): break
        if missing:
            say(f"  {len(missing)} paragraph(s) had no translation — translating them now")
            if not model_ready(a.provider): todo.append("Some paragraphs have no translation and the translation model could not be started (see check/missing.json)."); break
            got = translate_paragraphs([m["orig"] for m in missing], meta, a.provider, work)
            if got:
                for m, g in zip(missing, got):
                    m["trans"] = g
                    if m.get("note"): verify.append(f"page {m['page']}: a footnote «{m['orig'][:50]}…» was translated — confirm on the scan that it really is a footnote")
                json.dump(missing, open(chk / "missing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                run([PY, HERE / "apply_missing.py", rt, chk / "missing.json"])
            else: todo.append("The model could not translate the missing paragraphs consistently (see check/missing.json)."); break
        rows = json.load(open(chk / "alignment.json", encoding="utf-8")); changed = bool(fo or ft or missing)
        # what the checker leaves to a person: do the safe thing and note it
        for r in reversed([r for r in rows if r["hint"] and "auto-merge" not in r["hint"] and "MISSING" not in r["hint"]]):
            oi, oe = r["o"]; ti, te = r["t"]; h = r["hint"]
            if "cut-off tail" in h or "translation merged" in h:
                lo, hi = (oi, oe) if oe - oi >= 2 else (oi - 1, oe)          # a lone tail joins the paragraph before it
                if lo >= 0 and merge_raw(ro, "orig", lo, hi): changed = True; verify.append(f"page {r['page']}: a broken-off piece of text was joined to the paragraph before it — read that sentence once against the scan and mend it")
            elif "front-matter" in h:
                if delete_raw(ro, "orig", oi): changed = True; verify.append(f"page {r['page']}: a title-page line with no translation was left out")
            elif "EXTRA" in h:
                if te - ti == 1 and merge_raw(rt, "trans", ti - 1, te): changed = True; verify.append(f"page {r['page']}: an extra translated paragraph was folded into the one before it")
            elif "length ratio" in h:
                verify.append(f"page {r['page']}: one paragraph is much longer on one side — compare the two")
        if not changed: break
    if not aligned:
        rc, o = run([PY, HERE / "align_check.py", ro, rt, "--emit", chk]); aligned = rc == 0
    if not aligned:
        todo.append("These places still do not line up (the two texts are shown side by side):\n" + o)

    if aligned:
        say("\nStep 4 of 5 — building the PDF and the reader")
        title = meta["title"]; slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-")[:60]
        pdf = pathlib.Path(a.out).expanduser() if a.out else folder / f"{slug}.pdf"
        rc, o = run([PY, HERE / "md_edition.py", ro, rt, "--author", meta["author"], "--work", f"<i>{title}</i> ({meta['year']})", "--lang", *meta["lang"], "--edition", meta["edition"],
                     "--left-label", f"{LANGS.get(meta['lang'][0], meta['lang'][0])} · {meta['year']}", "--right-label", f"{LANGS.get(meta['lang'][1], meta['lang'][1])} translation", "-o", pdf, "--check-dir", chk, "--skip-check", "--preview", "1"] + (["--no-html"] if a.pdf_only else []))
        if rc: todo.append("The PDF could not be built:\n" + o[-2000:])
        else:
            say(f"  done → {pdf.name} and {pdf.with_suffix('.html').name}")
            prev = pdf.with_name(pdf.stem + "_preview")
            if prev.exists(): subprocess.run(["rm", "-rf", str(prev)])
    say("\nStep 5 of 5 — notes for you")
    todo = list(dict.fromkeys(todo)); verify = list(dict.fromkeys(verify))   # a check that ran twice is reported once
    lines = []
    if todo: lines += ["THINGS THE COMPUTER COULD NOT DECIDE — please fix, then run the same command again:", ""] + [f"• {t}" for t in todo] + [""]
    if verify: lines += ["WORTH A LOOK (the edition is built; these are spots to glance at):", ""] + [f"• {v}" for v in verify] + [""]
    lines += ["How to fix text: open the .refined.md file in TextEdit, search for the words shown, correct them, save, run the command again.",
              "Scan pages: `sbs scan \"folder of page images or PDF\" 46 -o .` writes scan-p46.png to look at."]
    (folder / "TO-DO.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if todo:
        say("  Not finished: see TO-DO.txt (opening it)."); subprocess.run(["open", str(folder / "TO-DO.txt")]); sys.exit(2)
    say(f"  Finished. {len(verify)} spot(s) worth a glance are listed in TO-DO.txt."); 
    if aligned and not a.yes: subprocess.run(["open", str(pdf)])


if __name__ == "__main__": main()
