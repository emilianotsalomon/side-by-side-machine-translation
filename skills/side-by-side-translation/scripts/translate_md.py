#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""translate_md.py — translate a cleaned Markdown/text source paragraph by paragraph, alignment guaranteed.

    python3 translate_md.py BOOK.ocr.refined.md --source es --target en -o BOOK.trans.md
        [--provider lmstudio|openai|anthropic|mock] [--base-url http://localhost:1234/v1] [--model NAME]
        [--glossary glossary.txt] [--chunk-chars 9000] [--jobs 1] [--resume] [--retries 3]

Why: a free-form LLM draft of a whole book skips paragraphs, merges OCR fragments and invents pagination.
This sends the normalised paragraphs in chunks, each paragraph tagged `[[i]]`, and accepts a chunk only if
every tag comes back exactly once, in order, with the same anchors (leading `(n)` note numbers, `N.` /
`IV.` numbering, an ALL-CAPS heading stays ALL-CAPS) and the same `[n]` page markers. A failed chunk is
retried, then split in half, then left as `[[i]] ⟪UNTRANSLATED⟫` so align_check.py reports it instead of
silently dropping it. Output is blank-line paragraph text (notes `(n) …`, markers kept), which both
builders accept in place of a translation .md/.txt.

Providers: `lmstudio` (default; OpenAI-compatible, http://localhost:1234/v1, first loaded model unless
--model), `openai` (--base-url + OPENAI_API_KEY), `anthropic` (ANTHROPIC_API_KEY; --model default
claude-sonnet-5), `mock` (echoes the source with tags, for testing the machinery). Progress is written to
OUT.progress.json after every chunk; --resume continues from it."""
from __future__ import annotations
import argparse, json, os, pathlib, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import functools
print = functools.partial(print, flush=True)   # progress lines reach a log file as they happen
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from md_prep import MD_SUFFIXES, normalize_md

LANG = {"es": "Spanish", "en": "English", "de": "German", "fr": "French", "it": "Italian", "pt": "Portuguese", "la": "Latin", "el": "Greek", "nl": "Dutch", "ru": "Russian"}
TAG = re.compile(r"\[\[(\d+)\]\]")
MARK = re.compile(r"\[(?:p\.\s*)?(?:\d{1,4}|[ivxlc]{1,6})\]")
PAGE_ALONE = re.compile(r"^\[(?:p\.\s*)?(?:\d{1,4}|[ivxlc]{1,6})\]$")
ROMAN = re.compile(r"^((?:XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\.)\s")
NOTE = re.compile(r"^(\(\d{1,3}\)|\d{1,3}\))\s")
NUM = re.compile(r"^(\d{1,2}\.)\s")


def load_paragraphs(path: pathlib.Path):
    raw = path.read_text(encoding="utf-8")
    text = normalize_md(raw, side="orig")[0] if path.suffix.lower() in MD_SUFFIXES else raw
    out = []                                             # (text, is_page_block)
    for b in re.split(r"\n\s*\n", text):
        b = b.strip()
        if b: out.append((b, bool(PAGE_ALONE.match(b))))
    return out


def is_caps(s): return len(s) < 120 and s == s.upper() and sum(c.isalpha() for c in s) >= 3


def anchors(s):
    s2 = re.sub(r"^\s*(?:\[[^\]]{1,8}\]\s*)+", "", s)
    m = NOTE.match(s2) or ROMAN.match(s2) or NUM.match(s2)
    return (m.group(1) if m else None, is_caps(s2), sorted(MARK.findall(s)))


SYSTEM = """You are a literary translator working on a scholarly parallel-text edition. Translate from {src} into {tgt}.
Rules, all mandatory:
1. The input is a list of paragraphs, each starting with a tag like [[12]]. Return EVERY paragraph, in the same order, each starting with its own tag, one paragraph per tag, separated by blank lines. Never merge, split, drop or add paragraphs. Never add commentary.
2. Keep page markers such as [23] exactly, placed at the word where the page turns in your translation. Keep note numbers such as (1) at the start of a note paragraph and note cues such as (1) inside the text. Keep numbering such as "IV." or "3." at the start of a heading. A paragraph written in CAPITALS is a heading: return it in CAPITALS.
3. Faithful, complete, in flowing {tgt} of the period's register; keep the author's sentence structure where {tgt} allows; keep foreign phrases and book titles in their original language (you may add the {tgt} in brackets once).
4. OCR blemishes in the source (a stray "|", a misread letter) are not content: translate the intended text.{glossary}"""


THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def call_openai(base, key, model, system, user, temperature=0.2, timeout=900, local=False):
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": temperature, "max_tokens": 8192, "stream": False}
    if local: payload["reasoning_effort"] = "none"     # LM Studio: the one switch that stops Qwen3.5/DeepSeek reasoning (tested 2026-09-20; chat_template_kwargs and /no_think do not)
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", method="POST", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key or 'lm-studio'}"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return THINK.sub("", json.load(r)["choices"][0]["message"]["content"])


def call_anthropic(key, model, system, user, timeout=600):
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST",
        data=json.dumps({"model": model, "max_tokens": 8192, "system": system, "messages": [{"role": "user", "content": user}]}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return "".join(b.get("text", "") for b in json.load(r)["content"])


def first_lmstudio_model(base):
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=5) as r: return json.load(r)["data"][0]["id"]
    except Exception as e: sys.exit(f"LM Studio not reachable at {base} ({e}). Start it: `lms server start` and `lms load <model>`, or use --provider anthropic.")


def parse_reply(reply, ids):
    """→ {i: text} if every tag appears exactly once in order, else None + reason."""
    parts = TAG.split(reply)
    got = [int(x) for x in parts[1::2]]; texts = [t.strip() for t in parts[2::2]]
    if got != ids: return None, f"tags {got[:8]}… expected {ids[:8]}…"
    return dict(zip(got, texts)), ""


def check_chunk(src_map, out_map):
    bad = []
    for i, s in src_map.items():
        t = out_map.get(i, "")
        if not t: bad.append((i, "empty")); continue
        sa, so, sm = anchors(s); ta, to, tm = anchors(t)
        if sa != ta: bad.append((i, f"anchor {sa!r}→{ta!r}"))
        elif so != to: bad.append((i, "heading case"))
        elif sm != tm: bad.append((i, f"markers {sm}→{tm}"))
    return bad


def repair_markers(s, t):
    """Copy the source's markers into t at the proportional word when the model dropped or misplaced them."""
    t = MARK.sub("", t); t = re.sub(r"\s{2,}", " ", t).strip()
    body = len(MARK.sub("", s)) or 1; removed = 0; ins = []
    for m in MARK.finditer(s): ins.append((round(len(t) * (m.start() - removed) / body), m.group())); removed += len(m.group())
    for pos, mk in sorted(ins, reverse=True):
        if pos <= 0: t = f"{mk} {t}".strip(); continue
        if pos >= len(t): t = f"{t} {mk}"; continue
        b = pos
        if t[b] != " ":
            l, h = t.rfind(" ", 0, b), t.find(" ", b); b = l if (h < 0 or (l >= 0 and b - l <= h - b)) else h
            if b < 0: b = len(t)
        t = (t[:b].rstrip() + " " + mk + " " + t[b:].lstrip()).strip()
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_file"); ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--source", required=True, help="BCP-47 code of the source language"); ap.add_argument("--target", required=True)
    ap.add_argument("--provider", choices=["lmstudio", "openai", "anthropic", "mock"], default="lmstudio")
    ap.add_argument("--base-url", default=None); ap.add_argument("--model", default=None); ap.add_argument("--api-key", default=None)
    ap.add_argument("--glossary", help="text file: one 'term → rendering' per line"); ap.add_argument("--chunk-chars", type=int, default=9000)
    ap.add_argument("--jobs", type=int, default=1, help="parallel chunks (API providers)"); ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--resume", action="store_true"); ap.add_argument("--temperature", type=float, default=0.2)
    a = ap.parse_args()
    src = pathlib.Path(a.source_file).expanduser(); out = pathlib.Path(a.output).expanduser(); prog = out.with_suffix(out.suffix + ".progress.json")
    items = load_paragraphs(src); paras = {i: t for i, (t, pb) in enumerate(items) if not pb}
    gl = ""
    if a.glossary: gl = "\n5. Glossary — use these renderings consistently:\n" + pathlib.Path(a.glossary).expanduser().read_text(encoding="utf-8").strip()
    system = SYSTEM.format(src=LANG.get(a.source, a.source), tgt=LANG.get(a.target, a.target), glossary=gl)
    base = a.base_url or ("http://localhost:1234/v1" if a.provider == "lmstudio" else "https://api.openai.com/v1")
    key = a.api_key or os.environ.get("ANTHROPIC_API_KEY" if a.provider == "anthropic" else "OPENAI_API_KEY", "")
    model = a.model or (first_lmstudio_model(base) if a.provider == "lmstudio" else "claude-sonnet-5" if a.provider == "anthropic" else "gpt-4.1" if a.provider == "openai" else "mock")
    if a.provider == "anthropic" and not key: sys.exit("ANTHROPIC_API_KEY not set")
    done = json.load(open(prog, encoding="utf-8")) if (a.resume and prog.exists()) else {}
    done = {int(k): v for k, v in done.items()}
    # chunks by characters, never splitting between a heading and the paragraph after it
    ids = [i for i in paras if i not in done]; chunks = []; cur = []; size = 0
    for i in ids:
        cur.append(i); size += len(paras[i])
        if size >= a.chunk_chars and not is_caps(paras[i]): chunks.append(cur); cur = []; size = 0
    if cur: chunks.append(cur)
    print(f"  {src.name}: {len(paras)} paragraphs, {len(done)} done, {len(chunks)} chunk(s) of ≈{a.chunk_chars} chars → {model} via {a.provider}")

    def ask(ids_):
        user = "\n\n".join(f"[[{i}]] {paras[i]}" for i in ids_)
        if a.provider == "mock": return "\n\n".join(f"[[{i}]] {paras[i]}" for i in ids_)
        if a.provider == "anthropic": return call_anthropic(key, model, system, user)
        return call_openai(base, key, model, system, user, a.temperature, local=(a.provider == "lmstudio"))

    def translate(ids_, depth=0):
        """→ {i: text}; recursive halving on persistent failure."""
        src_map = {i: paras[i] for i in ids_}
        for attempt in range(a.retries):
            try: reply = ask(ids_)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
                print(f"    chunk {ids_[0]}–{ids_[-1]}: request failed ({e}); retry {attempt + 1}"); time.sleep(2 + 3 * attempt); continue
            got, why = parse_reply(reply, ids_)
            if got is None: print(f"    chunk {ids_[0]}–{ids_[-1]}: {why}; retry {attempt + 1}"); continue
            bad = check_chunk(src_map, got)
            for i, why in bad:
                if why.startswith("markers"): got[i] = repair_markers(src_map[i], got[i])
            bad = [(i, w) for i, w in bad if not w.startswith("markers")]
            if not bad: return got
            print(f"    chunk {ids_[0]}–{ids_[-1]}: {len(bad)} anchor problem(s) e.g. {bad[0]}; retry {attempt + 1}")
        if len(ids_) > 1 and depth < 6:
            h = len(ids_) // 2; r = translate(ids_[:h], depth + 1); r.update(translate(ids_[h:], depth + 1)); return r
        print(f"    paragraph {ids_[0]} left UNTRANSLATED after {a.retries} attempts")
        return {ids_[0]: f"⟪UNTRANSLATED⟫ {paras[ids_[0]]}"}

    t0 = time.time()
    def run_chunk(c):
        r = translate(c); done.update(r)
        prog.write_text(json.dumps({str(k): v for k, v in done.items()}, ensure_ascii=False), encoding="utf-8")
        print(f"    ✓ chunk {c[0]}–{c[-1]} ({len(c)} paragraphs, {time.time() - t0:.0f}s)")
    if a.jobs > 1 and a.provider in ("openai", "anthropic"):
        with ThreadPoolExecutor(max_workers=a.jobs) as ex: list(ex.map(run_chunk, chunks))
    else:
        for c in chunks: run_chunk(c)
    # assemble in source order, page blocks kept in place
    lines = []
    for i, (t, pb) in enumerate(items):
        if pb: lines.append(t)
        else: lines.append(done.get(i, f"⟪UNTRANSLATED⟫ {t}"))
    out.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    unt = sum(1 for v in done.values() if v.startswith("⟪UNTRANSLATED⟫")) + sum(1 for i in paras if i not in done)
    print(f"  → {out} ({len(paras)} paragraphs" + (f", {unt} UNTRANSLATED — align_check.py will show them" if unt else "") + f", {time.time() - t0:.0f}s)")
    if not unt and prog.exists(): prog.unlink()


if __name__ == "__main__": main()
