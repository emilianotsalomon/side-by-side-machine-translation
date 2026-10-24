---
name: side-by-side-translation
description: "Bilingual side-by-side editions. (1) A scanned or printed book PDF with no translation yet → ONE PDF in one of two layouts, chosen by the user when the PDF comes in: a PHOTOCOPY edition (the original page on the left, new English typeset beside it, aligned line by line, original pagination kept — like the Hegel Encyclopaedia 1817 edition) or a CLEAN-TEXT edition (both columns retypeset, the original pagination marked in the margins with a red bar at each page break, footnotes at the foot — like the Exner edition, \"Trendelenburg style\"); triggers: \"scope and plan out a side by side translation\", \"facing edition\", \"keep original pagination\", \"give only output pdf\" — references/facing-edition.md, scripts/facing (OCR and all scan processing run locally with Tesseract/poppler/Chrome). (2) Two .txt, .md or .epub files (original + translation) → an HTML reader and a print-ready landscape PDF (table of contents, heading levels, notes in smaller type, page markers in [brackets]); two Markdown files have a fast lane: md_clean → align_check → md_edition. Trigger on: \"side by side\", \"parallel text\", \"bilingual\", \"facing translation\", \"compare original and translation\", \"side-by-side html\", \"parallel edition pdf\", \"print edition\", or when an existing side-by-side HTML should become a PDF."
---

# Side-by-side translation

Produces a scholarly parallel-text Artifact (Loeb Library style) from a source text and its translation, **and a print-ready PDF edition of the same text** (`scripts/build_pdf.py`, § PDF edition). Every build ends with **both files** on the Desktop — the HTML reader and the PDF — unless the user asks for only one. An existing side-by-side HTML can be turned into the PDF alone (§ PDF edition, input 2).

Supported input formats: `.txt` (plain text), `.md` (Markdown OCR or an LLM's Markdown translation — normalised on load, **§ Markdown sources**), `.epub` (auto-extracted), `.pdf` / scanned image (via Read tool).

---

## Scanned book, no translation yet → facing-page PDF (read only this, then `references/facing-edition.md`)

A PDF of a printed book to be translated, delivered as one PDF (the user's usual request: "scope and plan out a side by side translation for this into english. give only output pdf. keep original pagination; preserve stylistic choices"). **First question, before any scoping, unless the user already named the layout** — one `AskUserQuestion` with exactly these two options:
- **Photocopy edition** (like the *Hegel, Encyclopaedia 1817* edition): the original scanned page on the left, the new English typeset on the right, one spread per original page, every English block aligned to its original line; folios, signatures, ornaments as printed. → `book.json` `"layout": "facing"`.
- **Clean-text edition** (like the *Exner, Psychologie der Hegelschen Schule* edition; "Trendelenburg style"): both columns freshly typeset, original left / English right, paragraph rows aligned; the original pagination marked at the exact word where each page begins (number in the outer margin, thin red bar in the text), the author's footnotes at the page foot, chapters on new pages, a contents page. The scan is not reproduced. → `"layout": "retype"`.
Describe both in the question in plain words (a photocopy beside a translation vs. a clean re-typeset text), then follow **`references/facing-edition.md`**: scripts in `scripts/facing/` (set up with `new_book.py`, run through the `scripts/py` launcher — never a hard-coded Python path), briefs in `templates/facing/`, lean agent types in `agents/`. OCR and every other step that touches the scan run **on the local machine** (the PDF's own text layer via poppler, otherwise Tesseract; `doctor.py` checks the tools). The rules that decide its cost, in one line each:
- pass `effort` on every Agent call (translators and reviewers `medium`) — subagents otherwise inherit the session's effort, and at max/xhigh they cost 20–50× more per page;
- translators work two pages per `bundle.py` call (line-numbered OCR + reading-size views), no extra crops, no builds;
- ≤ 12 pages per translator, ≤ 25 per reviewer, so no agent's context passes ~180k (beyond that cache-breaking trims multiply the cost);
- after a usage-limit stop, fresh agents on the missing pages (`status.py`), not resumed ones;
- `book.json` instead of editing scripts; `make.py` builds and checks the whole book in one call; `usage.py` reports the true cost.
- finished editions go into the team corpus with `scripts/facing/corpus.py` (one Markdown file per book, original and English page by page) and the static reader `reader.py` (references/facing-edition.md § Corpus and reader);
- the clean-text layout is the same pipeline plus an `orig/` transcription per page; `make.py` builds either layout from `book.json` (`retype.py` → `build_pdf.py` for clean text; references/facing-edition.md § Clean-text edition).

---

## Markdown fast lane — two `.md` files in, PDF + HTML out (read only this when that is the case)

For an OCR `.md` (from the `ocr` tool: `[n]` markers, `#` headings, `[^n]` notes) and a translation `.md` (LLM output with `**[n]**` page blocks, or any Markdown). Six commands, no `.txt`, no hand-written analysis. Budget observed on a 63-page book (Llosa 1952, 175 paragraphs): 12 tool calls, 4 scan pages read, both deliverables. Do not `Read` the `.md` files or the scan wholesale: every report below is sized to be read in full.

**One step, no questions asked of the agent: `go.py`** (`python3 /SKILL_BASE/scripts/go.py ORIG.md [TRANS.md]`; on Emiliano's own Mac the optional `sbs` wrapper in `/opt/homebrew/bin` fronts it — not part of the skill, not needed elsewhere). It cleans, translates if needed, aligns, applies the safe fixes, translates skipped paragraphs with the model, builds, opens the PDF and writes a plain-language `TO-DO.txt`; it exits 2 with the to-do when something needs a person. Prefer it when the user just wants the edition; use the pieces below when you are diagnosing.

**At scale (a queue of old books): `book_run.py`.** One folder per book with a `meta.json` (`book_run.py --init DIR` writes the template: author, work, languages, edition or footnote, scan or OCR path, provider/model, glossary, labels, extra build flags). Then `python3 /SKILL_BASE/scripts/book_run.py BOOK1 BOOK2 … [--jobs 2]` runs, per book, `ocr → md_clean → translate_md → align_check → md_edition`, skipping stages whose outputs exist, and STOPS a book (not the queue) at the first report that needs judgement, written to `BOOK/STATUS.md` with the fixes to apply. The translation step is `translate_md.py`: paragraphs tagged `[[i]]`, sent in chunks to LM Studio (`lms server start`, `lms load qwen/qwen3.5-9b`; the script sends `reasoning_effort: none`, the only switch that stops Qwen3.5's reasoning — measured 4 paragraphs in 20 s), the OpenAI API or the Anthropic API; a chunk is accepted only when every tag, anchor and page marker comes back — so `missing.json` stays empty and the free-form-draft problems below never arise. Your part is the judgement session: settle the stopped books' `STATUS.md` items in one sitting, rerun `book_run.py` on them, look at the previews.

The six commands `book_run.py` wraps, for one book by hand:

```bash
SCRIPTS=/SKILL_BASE/scripts
# 0. No translation yet? Translate the CLEANED source with alignment guaranteed (after step 1):
python3 $SCRIPTS/translate_md.py "ORIG.refined.md" --source es --target en -o "TRANS.md" [--provider lmstudio|anthropic] [--glossary g.txt] [--resume]
# 1. Mechanical OCR clean-up → *.refined.md (originals untouched) + a list of pages to look at
python3 $SCRIPTS/md_clean.py "ORIG.md";  python3 $SCRIPTS/md_clean.py "TRANS.md" --side trans
# 2. Alignment: one compact report of every row that is not one-to-one, with proposed fixes
python3 $SCRIPTS/align_check.py "ORIG.refined.md" "TRANS.refined.md" --emit chk
python3 $SCRIPTS/fix_orig.py "ORIG.refined.md"  < chk/fixes_orig.json     # OCR-split paragraphs merged
python3 $SCRIPTS/fix_orig.py "TRANS.refined.md" < chk/fixes_trans.json    # translator splits merged
# 3. Only for what the reports flag (cut-off tails, garbled words, a (n) note to verify, a heading-level mix):
python3 $SCRIPTS/scan_page.py "SCANDIR-or-PDF" 46 53 -o chk    # → Read the PNGs, then one fix_orig.py list
# 4. Paragraphs the translation skipped: fill "trans" in chk/missing.json (yourself; a subagent if > ~8), then
python3 $SCRIPTS/apply_missing.py "TRANS.refined.md" chk/missing.json
# 5. Build (re-runs the check; exit 2 = back to step 2). Both deliverables + previews of page 1 and a middle page
python3 $SCRIPTS/md_edition.py "ORIG.refined.md" "TRANS.refined.md" --author "…" --work "<i>…</i> (YEAR)" \
    --lang es en --footnote "…" -o ~/Desktop/Title.pdf        # or --edition "the first edition of YEAR"
```

Then Read the two preview PNGs, deliver PDF + HTML with `SendUserFile`, publish the `.fragment.html` with the Artifact tool, delete the preview folder.

What each report means, in one line each:
- `md_clean`: counts of debris repaired; **flagged** items are not changed — a lowercase heading such as `osas.` is the cut-off tail of the previous paragraph (needs the scan, p. given); `#`/`##` both present means the OCR guessed levels from type size: check one heading of each on the scan; old books usually set all sections alike → `fix_orig.py FILE --regex '^# (?!TITLE)' '## '`.
- `align_check`: `1:0 MISSING` → missing.json; `k:1 OCR split → auto-merge` (safe, applied by fixes_orig.json); `translation matches Oₖ alone → others MISSING` (LLM skipped a paragraph); `(n) note with no counterpart` → look at the scan before translating — the OCR of old books turns a page's last line into a note; `translator split → auto-merge` (fixes_trans.json); `front-matter line with no counterpart` → repair the half-title OCR or join the two title lines; a `1:1` with a length ratio far from 0.9–1.05 → the translation lost or added text there.
- `missing.json` entries carry the anchor paragraph; write `trans` in the file's own convention (`[^n]: …` for a note in Markdown). `apply_missing.py` refuses nothing silently: it reports anchors it could not find.
- `md_edition`: front matter (several heading rows before the first paragraph) stays out of the contents; run-in titles nest at level 3; `--` passes anything else to `build_pdf.py` (`-- --facing --trim 6x9`).

Rules that keep it cheap: never merge or split by editing normalised dumps — the `.refined.md` files are the sources and every tool re-reads them; fix strings must match the raw Markdown (`# `, `**`); 15–25 scan pages would cost more than the whole rest of the run — read only flagged ones; the translation's own page blocks are ignored, the original's markers are copied across, so never spend calls repairing an LLM's pagination; leave the translation's wording alone unless the OCR misled it (the garbled spots) — the user's standing instruction is "add only what was missing".

---

## Token economics and safety rules (measured, September 2026)

**Translating a book — cost per path, for 157k words of French (Blondel 1935):**

| path | tokens | money | wall clock | when |
|---|---|---|---|---|
| `translate_md.py --provider anthropic --model claude-sonnet-5 --jobs 4` | ≈ 450k (input + output once) | a few dollars | < 1 h | **default for anything over ~20k words** when an API key exists |
| Sonnet sub-agents via `chunk_tools.py` (13 × 9–12k words) | ≈ 2.4M sub-agent tokens (60k fixed + 7k per 1k words each; every turn re-reads the context) | plan allowance | ≈ 50 min | no API key; keep agents to 3 turns with `prompts.md`; > 6.5k words → two-step write, else they stall (~150k wasted each) |
| local Qwen 27B / 9B via `translate_md.py` | none | none | overnight / hours | free; `reasoning_effort: none` is sent automatically |
| the orchestrator translating inline | its own context, ~2× the text | — | — | only under ~5k words |

Where the orchestrator's own tokens go, and the rule that keeps them small: never print paragraphs — `align_check` prints only the non-1:1 rows; never read the sources with Read — the reports are sized to be read whole; read only scan pages a report names (≈1.5k tokens each); previews: page 1 and one middle page; a critic reads `chunk_tools.py sample` (≈40 pairs, 8k words), not the book.

**Safety rules learned the hard way:** (1) a `(n)` note the translation lacks is NOT translated and inserted automatically — the OCR of old books turns a page's last line into a note; look at the scan first (`go.py` stops on it unless `--auto-notes`); (2) `md_clean.py` never runs on French without `--lang fr` (it detects French anyway): the space before `; : ? !` is typography, not debris; a clean digital transcription (RTF, EPUB) needs no cleaning at all; (3) `fix_orig.py` refuses a list whose `old` is absent — never fall back to blind regex on the whole file; (4) refined copies are edited, originals are never touched; (5) files from Les Classiques des sciences sociales and similar sites are for personal use — the footnote credits the transcriber, the edition is not redistributed; (6) translators' doubts go to `flags.md`, the footnote says the translation is machine-made and unrevised.

---

## Step 0 — Decision tree (read before anything else)

**0. Target language?**
- If the user said "translate" without specifying a target language, **ask** before proceeding. Do not assume English — infer from context (user's language, email, previous messages) but confirm.

**1. Source format?**
- **EPUB** → pass `.epub` path directly; skip to Q2.
- **Markdown** (`.md` from the `ocr` tool or HathiTrust, and/or an LLM's translation with `**[n]**` page blocks) → pass the `.md` paths directly to both builders; there is no .txt step. Refine by editing the `.md` files with `fix_orig.py` and re-running (**§ Markdown sources**). If the translation already exists, Q3 does not apply.
- **Plain text, blank-line-delimited** → skip to Q2.
- **HathiTrust OCR** (file has `## p. XX` markers) → **one command**: `--hathitrust-prep` (see **§ Flat-stream OCR text**), then Q2.
- **Scanned-book OCR export** (PDFgear, ABBYY, Acrobat, Tesseract: one line per printed line, standalone page numbers, running headers, no blank lines) → **one command**: `--book-ocr-prep` (see **§ Flat-stream OCR text**), then Q2 and **§ Chunked translation loop**.
- **Other flat-stream OCR** (no blank lines, no `## p.` markers — some Gutenberg) → use `--detect-paragraphs` or see **§ Flat-stream OCR text** Strategy B.
- **PDF with selectable text** → search Gutenberg/archive.org/Wikisource first; if found, treat as plain text. Otherwise **one command**: `scripts/pdf_bbox_paras.py` (see **§ PDF with a text layer**) rebuilds the paragraphs from the line geometry and writes `[n]` page markers; do not read the pages with the Read tool.
- **Scanned PDF / photograph** → to be translated and delivered as one PDF: ask **photocopy edition or clean-text edition** (the two options at the top of this file, Hegel-Encyclopaedia style vs. Exner style), then `references/facing-edition.md`. Only when a reflowed HTML reader is wanted instead: **§ PDF & OCR sources**; for > 12 pages, follow chunked-write protocol.
- **Pasted into chat** (no file at all) → see **§ Text pasted in chat**. Q3 does not apply: you transcribe and translate it yourself, in paired chunks.

**2. Custom design needed?**
- Yes, or rich structure (headings, front matter, numbered sections) → `--json-only`.
- No → `--artifact`. Add `--toc` for texts with chapters or numbered sections.
- Either way, the PDF follows from the same `orig.txt` / `trans.txt` (§ PDF edition) — plan the title-block facts (author, work, edition, languages) while you read the source.

**3. Source length?**
- Under ~1,000 words → translate inline.
- Source already in your context (pasted, or just read with the Read tool) → translate it yourself in paired chunks (§ Text pasted in chat). A subagent would re-read what you already hold and gain nothing.
- Longer source in a file, any length (a 30,000-word chapter is fine) → **§ Chunked translation loop**: prep `orig.txt`, then show → translate → append, one pass. This is the cheapest path: every source token enters context once and every translated token leaves once. Do not spawn a translation subagent unless the user asks for agents or the main context is already heavy (e.g. after reading a scanned PDF page by page) — then see **§ Translation subagent**.

---

## § EPUB sources

Pass the `.epub` path directly — no pre-processing needed:

```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/original.epub /abs/path/trans.txt \
  --artifact --toc --title "Title" \
  --left-label "German, 1901" --right-label "English Translation" \
  -o /abs/path/output.html
```

To inspect or edit the extracted text before alignment, extract to a file first:

```python
import pathlib, sys
sys.path.insert(0, '/SKILL_BASE/scripts')
from side_by_side_html import extract_epub_text
text = extract_epub_text(pathlib.Path('/abs/path/original.epub'))
pathlib.Path('/SCRATCHPAD/orig.txt').write_text(text, encoding='utf-8')
print(len([b for b in text.split('\n\n') if b.strip()]), 'paragraphs')
```

Then fix any issues and pass `orig.txt` to the script instead of the `.epub`.

**Common issues:** figure captions create false paragraph splits (look for blocks starting with a lowercase letter); `nav.xhtml` in the spine adds spurious short blocks; `<h1>–<h6>` elements become standalone paragraphs — merge with `re.sub(r'^(Title)\n\n', r'\1 ', text, flags=re.MULTILINE)`.

---

## § Flat-stream OCR text (HathiTrust / Gutenberg)

Flat-stream OCR has no blank lines between paragraphs — the entire page is one block. HathiTrust files have `## p. XX` page markers.

**HathiTrust files — one command** (preferred; handles everything automatically):
```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/hathitrust-download.txt /dev/null \
  --hathitrust-prep -o /SCRATCHPAD/orig.txt
```
This strips page markers, running headers, standalone page numbers, OCR garbage; joins wrapped lines; merges page-boundary continuations; splits on structural markers (§ sections, `Anmerkung.`, all-caps headings, Roman-numeral chapters); fixes line-break hyphenation; and distinguishes section-heading `§ N` from cross-references like `vgl. § 10` using consecutive-run heuristics. Output is clean blank-line-delimited paragraphs ready for translation. **Do not write manual cleaning scripts — this replaces all of that.**

After running, verify the count looks sane and spot-check a few paragraphs. Then proceed to translation.

**Scanned-book OCR exports (PDFgear, ABBYY, Acrobat, Tesseract) — one command:**
```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/PDFgear_OCR.txt /dev/null \
  --book-ocr-prep -o /SCRATCHPAD/orig.txt
```
Drops standalone page numbers, running headers (any short unpunctuated line that recurs 3+ times, plus garbled near-copies of it) and `- Author, Title` signature lines; joins wrapped lines and end-of-line hyphenation; starts a paragraph where the previous line is short and ends a sentence, or where a line opens with a marginal title (`Heraklit. — …`, also when the OCR lost the period before it); merges leading ALL-CAPS title lines into one heading. It prints the count and warns about over-long lines that look like a running header spliced into the text at a page break. Expect ~95% of paragraph boundaries to be right on a clean 1920s–1950s typeset book; fix the rest while translating (§ Chunked translation loop). Do not hand-write a cleaner — extend this one if a new OCR quirk appears.

What it cannot do: restore periods the OCR dropped at sentence ends (`hält Blicken`), fix misread names (`Piaton`), lowercase the Title-Cased heading, or remove a header spliced mid-line. Those are `scripts/fix_orig.py` jobs, done chunk by chunk as you read.

**Non-HathiTrust flat-stream OCR** (no `## p.` markers — some Gutenberg):

**Strategy B — Heuristic paragraph detection** (continuous prose):
```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/orig.txt /abs/path/trans.txt \
  --detect-paragraphs --artifact --title "Title" -o /abs/path/out.html
```
Inserts blank lines where a line ends with `.!?` (excluding known abbreviations) and the next starts with an uppercase letter. Verify the paragraph count looks sane before translating.

---

## § PDF with a text layer (justified re-typesetting, offprint, modern book PDF)

`pdftotext` alone loses the paragraphing (no blank lines, one line per printed line). The line geometry has it: in justified text every line but the last of a paragraph reaches the right margin.

```bash
python3 /SKILL_BASE/scripts/pdf_bbox_paras.py /abs/path/book.pdf -o /SCRATCHPAD/orig.txt --probe   # margins histogram
python3 /SKILL_BASE/scripts/pdf_bbox_paras.py /abs/path/book.pdf -o /SCRATCHPAD/orig.txt           # write paragraphs
```

Rules: a line that stops short of the right margin **and** ends in terminal punctuation closes a paragraph (a short line without punctuation is a manual line break and continues); an indented line opens one (list items `1°`, `a)`); a line with no lowercase letters is a heading, left-aligned or centred, one or two lines; end-of-line hyphens are joined; every page start is written inline as `[n]` before the first word of the page. It prints every paragraph under 130 characters — check that list: it should be exactly the headings plus real short items. Then, by hand with `fix_orig.py`: drop the PDF's own title block, join a bare part numeral to its title (`II` + `EL TIEMPO…` → `II. EL TIEMPO…`, otherwise the TOC shows a bare `II` and the PDF prints `Ii.`), restore accents the typesetter dropped in capitals (`DISPOSICION` → `DISPOSICIÓN`), and leave the numbering as found (do not invent `V`, `VI` for later essays that carry no numeral — say so in the footnote).

**A re-typeset text layer is usually an uncorrected OCR.** Expect a few hundred slips in 60,000 words and fix them chunk by chunk as you translate (§ Chunked translation loop). Patterns seen in a 1960s Spanish typesetting, all safe as whole-word global replacements after a grep of their contexts: `per`→`por` (not *per se*), `pare`→`para`, `paste`→`parte`, `pass`→`para`, `tas`→`las`, `sine`→`sino`, `dei`→`del` (not *vestigia Dei*), `1o`/`1os`→`lo`/`los`, `bacterial`→`bacterias`, `tares`→`tarea`, the conjunction `e` read as `a` before *i-/hi-* (`oxígeno a hidrógeno`), `Homo`→`como`, lost dashes around asides (`declara` → `—declara—`), a period lost or added at sentence ends. Verify any regex that touches capitalisation against the raw `pdftotext` dump before applying it: one that swallowed the space after sentence-initial `La` cost a critic pass to find. Keep the fix lists; the edition's footnote says "obvious typographical errors have been corrected silently".

---

## § PDF & OCR sources

**Selectable text:** use Read tool → clean (join broken lines, remove headers/footers) → save as `.txt`.

**Scanned image:** use Read tool with `pages` parameter. ⚠ Each image page costs ~1,000–2,000 tokens; factor this in. Rules:
- Read at most **20 pages per call** (hard limit); maximise pages per call.
- If early pages return `[media removed: request limit]`, re-read in a later call.
- For scans of **≤ 12 pages**, skip the chunked-write protocol: read all pages (in batches of ≤ 20), transcribe the full text, and write `orig.txt` in one pass.
- For scans of **> 12 pages**, **follow § Chunked-write protocol** — reading all pages before writing causes unrecoverable context resets.

**Batch size guide:**

| PDF type | Recommended batch |
|---|---|
| Clean modern typeset | **10–12 pages** |
| Degraded / small print / dense footnotes | **6–8 pages** |
| Handwritten, manuscript, blurry scan | **4–5 pages** |

When in doubt, read a 2-page sample first.

---

## § Chunked-write protocol (mandatory for image PDFs)

> **Never read all pages before writing.** Every batch read without writing to disk is lost to a context reset.

**Step A — Before page 1:** create `SCRATCHPAD/orig.txt` (empty) and `SCRATCHPAD/orig.progress` with `"0/N"`.

**Step B — Loop:** Read batch → transcribe complete paragraphs → append to `orig.txt` AND update `orig.progress` → repeat.

**Step C — Cross-page paragraphs:** when a paragraph runs off the end of a batch, include it in the next batch (re-read the last visible sentence as overlap and write the whole paragraph when it completes).

**How to append (always use Python — `Edit` and heredoc corrupt non-ASCII):**
```bash
python3 << 'PYEOF'
# -*- coding: utf-8 -*-
import pathlib
f = pathlib.Path('SCRATCHPAD/orig.txt')
f.write_text(f.read_text(encoding='utf-8') + """

PARAGRAPH_TEXT_HERE

NEXT_PARAGRAPH_HERE
""", encoding='utf-8')
PYEOF
echo "M/N" > SCRATCHPAD/orig.progress
```
For very large batches, write to a temp `.py` file instead to avoid shell quoting limits.

**Step D — After final chunk:** count paragraphs and pass N to the translation subagent:
```bash
python3 -c "import re,pathlib; t=pathlib.Path('SCRATCHPAD/orig.txt').read_text(); print(len([p for p in re.split(r'\n\n+',t) if p.strip()]),'paragraphs')"
```

**Recovery after context reset:** read `orig.progress` for the last page written, read the last 20 lines of `orig.txt` to confirm where you left off, resume from the next page. If `orig.progress` doesn't exist, start over from page 1.

---

## § Text pasted in chat (or otherwise already in context)

(For a source that lives in a file and is *not* yet in context, use **§ Chunked translation loop** below instead — it reads and translates slice by slice.)

The source is already in your context, so the cheapest workflow is one pass: for each chunk of 8–20 paragraphs, write the cleaned source **and** its translation in the same call with `scripts/append_pairs.py`. Never write the whole source first and translate afterwards — that is two passes over the same text, and a count mismatch then surfaces only at the end.

```bash
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys; sys.path.insert(0, '/SKILL_BASE/scripts')
from append_pairs import append
O = ["""
3. Sobre la técnica (1)
""","""
(1) Publicado por primera vez en …
""","""
Un profesor de Filosofía … (2)
"""]
T = ["""
3. On Technology (1)
""","""
(1) First published in …
""","""
A professor of Philosophy … (2)
"""]
append('/SCRATCHPAD/orig.txt', '/SCRATCHPAD/trans.txt', O, T)
PYEOF
```

- `append` refuses the chunk if the two lists differ in length or a leading `(N)` / heading number differs, so alignment is guaranteed chunk by chunk and `--verify` passes at the end.
- Keep the `# -*- coding: utf-8 -*-` line: on some locales `python3 -` rejects non-ASCII stdin without it, and a failed chunk costs the whole chunk again.
- Start and end each triple-quoted string on its own line (a paragraph ending in `"` otherwise breaks the closing quotes).
- Clean as you transcribe: join OCR line breaks and hyphenation, drop page folios and running headers, fix obvious OCR misspellings in names and foreign titles. Rebuild paragraphs that OCR split at a page break around a footnote block, and place each `(N)` note after the paragraph that cites it (§ Footnote handling).
- To append several chunks in one tool call, save each as `cN.py` and run them in order (`python3 c12.py && python3 c13.py`). Order matters: never run appends in parallel, and never nest a literal `PYEOF` line inside a heredoc that uses that delimiter.
- Finish with `--verify`, then build the HTML and the PDF (Fast path). State in your final message how the key recurring terms were rendered.

---

## § Chunked translation loop (source in a file, any length)

One pass over the source: read a slice of `orig.txt`, translate it, append it, read the next slice. Nothing is read twice, nothing is buffered in context, and every append is checked against the source, so drift is caught at the chunk, not at the end.

Per chunk, **one tool call** does three things, in this order:

```bash
# 1. OCR corrections for the slice you just read (optional; "\n\n" in `new` splits a paragraph)
python3 /SKILL_BASE/scripts/fix_orig.py /SCRATCHPAD/orig.txt <<'EOF'
[["Piaton", "Platon"], ["Wirkliche sieht Mit", "Wirkliche sieht. Mit"],
 ["erlitten werde! Platon. - In der", "erlitten werde!\n\nPlaton. — In der"]]
EOF
# 2. append the translation of [12]..[27]  (START = paragraphs trans.txt holds now)
python3 /SKILL_BASE/scripts/append_trans.py /SCRATCHPAD/trans.txt 12 --orig /SCRATCHPAD/orig.txt <<'EOF'
…one translated paragraph per blank-line-separated block, same order and count as [12]..[27]…
EOF
# 3. show the next slice
python3 /SKILL_BASE/scripts/show_paras.py /SCRATCHPAD/orig.txt 28 42
```

- **Chunk by characters, not paragraphs**: 15–25k characters of source per slice (roughly 2,500–4,000 words). `show_paras.py` stops at 30k characters and says where to resume; tool output beyond ~40 KB is written to a file instead of shown, which costs a second read.
- **Fix before you append.** A split or merge in `fix_orig.py` shifts every index after it. Do it in the same call, *before* `append_trans.py`, and count the resulting paragraphs when you number the chunk.
- Splits you will need: a marginal title the cleaner left inside the previous paragraph (`gehandelt Die Mystik der Renaissance. -`) and a heading glued to its body paragraph. Merges you will need: a paragraph cut at a wrapped closing quotation mark (a block starting with `", d. i.` or `', so doch`).
- `append_trans.py` refuses the chunk if `trans.txt` does not hold exactly `START` paragraphs, if the chunk would run past the end of the source, or if a leading `(N)` / `N.` / `IV.` anchor differs from the source at the same index. A refusal costs only that chunk.
- Never use plain `python3 -c` string replacement for fixes: `fix_orig.py` aborts when an `old` string is absent, which is how a typo in a fix list gets caught.
- Build the glossary from the first chunk (see § Translation subagent for what to look for), keep it consistent, and state the key renderings in the final message.
- Finish with `--verify`, then build with `--toc` and `--html-copy ~/Desktop/Title.html`, then the PDF (§ PDF edition).

Budget observed for a 28,000-word German philosophy chapter: 8 chunks, ~45k tokens of source in, ~40k tokens of translation out, no subagents, ~15 tool calls end to end.

---

## § Markdown sources — how the builders read `.md`

The fast lane above is the workflow; this is what happens underneath. Both builders accept `.md` / `.markdown` anywhere a `.txt` is accepted. On every run `scripts/md_prep.py` normalises the file in memory and prints a one-line report per side, so **the `.md` files stay the single source of truth**.

| Markdown | becomes |
|---|---|
| `# Title`, `## Title` | a standalone heading paragraph; the `#` depth is kept as `md_level` → PDF heading level h1/h2/h3 and TOC level tc0/tc1/tc2 (`--no-md-levels` in `build_pdf.py`, `--toc-kind` in the HTML builder override it) |
| `[^1]: text` / inline `[^1]` | a `(1) text` note paragraph / `(1)` |
| standalone `[12]` or `**[12]**` | original: a `[12]` block for the aligner (page_after / page_mid). **Translation: dropped** — an LLM's page blocks rarely match the book; the original's inline markers are then copied into the translation at the proportional word (`--no-propagate-markers` to stop that) |
| one paragraph per line (LLM output) | one paragraph each; a line ending mid-sentence or in a hyphen is a soft wrap and continues; a short ALL-CAPS or numbered line is a heading and never joins |
| `**bold**`, `*italic*`, `` `code` ``, `[link](url)`, `\-` escapes, `- ` bullets, `---` rules, images | stripped |
| `Here is the complete translation…`, `Let me know if…`, `*(Title Page / Blank)*` | dropped as preamble / postamble / placeholder |
| `# o`, `# osas.` (OCR debris that became a heading) | kept and flagged — `md_clean.py` drops the < 3-letter ones, the rest need the scan |

Gotcha: a heading whose `#` depth is wrong for the book is fixed in the `.md` (`fix_orig.py FILE --regex '^## LA ONTOLOGIA' '# LA ONTOLOGIA'`), not with flags — the next run picks it up in both deliverables.

---

## § Saving to `.txt` — formatting rules

- One blank line between paragraphs, none within.
- **Section markers (§ 1., Kap. I, chapter titles, `a)`–`f)` subsections) must be standalone paragraphs** — one blank line before and after. The TOC auto-detects them from the DATA array; if they are glued to the body paragraph, the TOC misses them and the heading doesn't render as a divider. If OCR or the source has them inline, split them out:
  ```bash
  # Detect and split embedded headings automatically:
  python3 /SKILL_BASE/scripts/split_headings.py /SCRATCHPAD/orig.txt /SCRATCHPAD/trans.txt --dry-run
  # Review the report, then run without --dry-run to apply:
  python3 /SKILL_BASE/scripts/split_headings.py /SCRATCHPAD/orig.txt /SCRATCHPAD/trans.txt --report
  ```
  Or fix manually with `fix_orig.py` when the automatic splitter misses an edge case (e.g. a heading with no period, or a heading at an unusual position).
- Page numbers and running headers are auto-stripped by the script (see § Page number formats). A heading written as a number plus an ALL-CAPS title (`3 SOBRE LA TÉCNICA`) matches the page-marker pattern and is silently dropped — write numbered headings as `3. Sobre la técnica`.
- Heading paragraphs must stay under 120 characters; longer paragraphs starting with a Roman numeral (an enumerated question such as `I. ¿Cuáles serían…?`) are treated as body text, not TOC entries. If such an item is short, write it `I.—` to keep it out of the TOC.

---

## § Structured OCR text with embedded headings

OCR exports from printed books (PDFgear, ABBYY, HathiTrust) routinely glue structural markers — `§ 6.`, `ERSTES KAPITEL`, `a)` subsection labels, Roman-numeral headings — to the body paragraph before or after them. This creates two problems:

1. **TOC misses the heading** — `dTE()` only checks standalone short paragraphs.
2. **`isH()` doesn't style it as a divider** — it checks whether the entire paragraph is short and all-caps.

**Workflow:**

1. **After `--book-ocr-prep` or `--hathitrust-prep`**, run `split_headings.py --dry-run` to detect embedded headings.
2. **Review the report.** False positives: a body paragraph that starts with a Roman numeral used for enumeration (not a heading), or a parenthetical `a)` inside a sentence. These are rare but happen.
3. **Apply the splits.** Run without `--dry-run`. The script handles both `orig.txt` and `trans.txt` in tandem.
4. **For headings the script misses** (OCR garbled the `§` into `$` or `S`, heading has no trailing period, Greek subsection labels like `α)`), use `fix_orig.py` to fix the OCR first, then re-run `split_headings.py`.
5. **Verify alignment**: `--verify` after every split pass.

**Common OCR heading corruptions:**
- `$6` or `$17` → `§ 6` / `§ 17` (dollar sign for section sign)
- `S15` → `§ 15` (uppercase S for §)
- `KAPJTEL` → `KAPITEL` (OCR misread)
- Missing period after `§ N` — add it so the regex matches

**The 3-level TOC** (`tc0`/`tc1`/`tc2`) auto-detects:
- `tc0` (chapter): ALL-CAPS headings, KAPITEL/TEIL/CHAPTER, keyword headings (Appendix, Preface, Einleitung, Zwischenbetrachtung), marginal run-in titles, Roman numerals (when `chapters='roman'`)
- `tc1` (section): `§ N` sections, Arabic-numbered headings, Roman numerals (when `chapters='arabic'`)
- `tc2` (subsection): `a)`–`z)` and `α)`–`ω)` labels

Page markers `[XX]` in the text are auto-styled with the `.pg` class (small, muted, sans-serif).

---

## § Footnote handling

- Each footnote or group of footnotes becomes its own paragraph, prefixed by its marker: `(1)`, `(*)`, `**`, etc.
- Place footnote paragraphs after the paragraph containing the last reference to them on that page.
- When multiple short footnotes appear together (e.g., a bibliographic list), group them in a single paragraph: `(1) Lipps — "Fundamentos de la Estética". (2) Meumann — "Sistema de Estética".`
- Bibliographic references in footnotes: keep titles in their original language in both the source and translation columns.
- OCR of a printed book interleaves footnote blocks at page bottoms, often splitting a body paragraph in two. Rejoin the body paragraph first, then place the notes after it; note numbers in the body are usually garbled or missing in OCR — reinsert them as `(N)` at the citing word.

---

## § Translation subagent

**Book-length, in parallel (the settled way, Blondel 1935: 157k words, 13 Sonnet sub-agents, ~50 min):** `scripts/chunk_tools.py split SRC.md DIR --words 12000 --source fr --target en --glossary g.txt` writes `DIR/chNN.src.md` (paragraphs tagged `[[i]]`, never cutting a heading from its paragraph) and `DIR/BRIEF.md`. Spawn one sub-agent per chunk (model sonnet, background) with: read BRIEF.md, read chNN.src.md, write chNN.trans.md in the same tagged shape, run `chunk_tools.py verify DIR/chNN` until ✓, report one line. Sub-agents stall on a single >12k-word write: for chunks over ~10k words tell them to write in two Write-then-append steps, or split the chunk (`chNNa`/`chNNb`, concatenate afterwards and verify `chNN`). Then `chunk_tools.py status DIR`, `assemble DIR -o TRANS.md` (one paragraph per tag whatever line breaks they typed), `align_check`, `--verify`, a grep for glossary consistency across chunks (glosses of the same Latin word, capitalised terms), and the build. A digital source (RTF via `rtf_to_md.py`, EPUB) needs no md_clean — and md_clean must NOT run on French text (it strips the space before `;` `:` `?` `!`).

For texts over ~1,000 words, spawn a subagent. **Give the file path — never paste source text inline.**

**Building the glossary:** Before spawning the subagent, scan `orig.txt` for:
- Repeated capitalized terms or phrases (e.g., "lo estético", "la vivencia")
- Terms in scare quotes or with special emphasis (e.g., "substancia psíquica")
- Technical vocabulary specific to the discipline (philosophical, legal, scientific)

List 8–20 key terms with their intended translations. Consistency across the whole text matters more than any single rendering.

---
Read `/SCRATCHPAD/orig.txt`. It contains **N paragraphs** (blank-line-separated).

Translate from SOURCE LANG to TARGET LANG and write to `/SCRATCHPAD/trans.txt`.

GLOSSARY (use these terms consistently):
- TERM_1 → TRANSLATION_1

Rules:
- Flowing prose. One blank line between paragraphs, none within.
- **Preserve structural markers exactly**: chapter headings (Roman numerals, "Anhang"/"Appendix"), section labels, and footnote numbers (e.g. `1)`, `2)`) must appear at the **same paragraph index** in the translation as in the original. If the original's paragraph N starts with "IV. Der Auffassungsakt.", your paragraph N must start with "IV. The Act of Apprehension." Never merge a heading paragraph with the body paragraph that follows it, and never split a body paragraph to compensate for a merge elsewhere.
- Preserve embedded foreign phrases: translate then give original in brackets, e.g. "nothing is in the intellect [nihil est in intellectu]".
- Do not split paragraphs the original keeps as one unit.
- Do not merge paragraphs the original keeps separate — even if one appears to be a broken continuation (e.g. a sentence fragment at a page boundary). Translate each paragraph as given; alignment fixes happen upstream.
- Do not add headings, commentary, or translator's notes.
- Preserve footnote markers (*, **, numbered) and bibliographic titles in their original language.

After writing, verify the count matches N (use the one-liner from § Chunked-write Step D, substituting `trans.txt`). If count ≠ N, find and fix each discrepancy. Return only: "Done. N paragraphs written to /path/."

---

---

## § Checking alignment

After the subagent writes `trans.txt` (or after any manual edit), **always run `--verify`** (not just `--count`):
```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/orig.txt /abs/path/trans.txt --verify
```
This checks:
1. Paragraph counts match (same as `--count`)
2. **Anchor alignment**: Roman-numeral chapter headings, numbered footnotes (`N)`), and Anhang/Appendix markers appear at the same paragraph index in both files
3. **Page markers** `[n]` / `[p. n]` are the same set in both columns of every pair (the translation must carry each marker at the corresponding word)
4. **Heading parity**: a short ALL-CAPS paragraph on one side is one on the other, so the TOC and the divider styling fire in both columns

Exits **0** when both pass, **1** on any issue. `--count` alone catches gross mismatches but **misses offset errors** where the translator merged one paragraph and split another to keep the count equal — the most common silent failure mode.

`--artifact` also runs alignment verification automatically during build and prints warnings (but does not abort).

---

## § If the script exits with a paragraph mismatch

| Pattern | Cause | Fix |
|---|---|---|
| orig ≈ 2× trans | Section marker standalone | `re.sub(r'(§\.\s*\d+\.)\n\n', r'\1 ', text)` |
| trans > orig | Translator split long paragraphs | Merge in trans file |
| differs by small N | Translator added/removed a paragraph | Diff first/last paragraphs manually |

**Irregular mismatch:** spawn a subagent — loading both large files into the main context is costly.
> Read `orig.txt` (N paragraphs) and `trans.txt` (M paragraphs). Diagnose paragraph by paragraph (give index, type: missing/extra/split/merged, quote affected text). Fix in trans.txt. Verify count. Write corrected file back. Return: "Fixed. N paragraphs in [path]."

---

## § Page number formats

Auto-detected and stripped: `221`, `221 CHAPTER TITLE`, `TITLE 221`, `[221]`.

Other formats (`p. 221`, `— 221 —`) must be stripped manually before running.

---

## Fast path — default design

```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/ORIG.txt /abs/path/TRANS.txt \
  --artifact [--toc] \
  --title "Title" \
  --left-label "Language · Year" \
  --right-label "English Translation" \
  -o /abs/path/OUTPUT.html
```

Markdown inputs: pass the `.md` files in place of the `.txt` (§ Markdown sources). `--toc` adds a fixed left sidebar with scroll-spy (for texts with chapters or numbered sections, and for books whose sections are marginal run-in titles like `Heraklit. — …`). Numbered headings are classified by their number even when set in capitals (`1. DISPOSICIÓN …` → section, `II. EL TIEMPO …` → chapter); only *unnumbered* all-caps lines are chapters by case alone. Leading `[n]` markers are ignored for detection. A heading the rules get wrong is forced with `--toc-kind IDX=tc0|tc1|tc2|none` (e.g. the Roman-numbered sections of one essay in a book whose parts are also Roman: `--toc-kind 313=tc1`); `--toc-debug` shows the result including forced entries. Add `--html-copy ~/Desktop/Title.html` to also get a full standalone document (the `--artifact` output is a fragment without doctype/head). By default Roman-numeral headings are top-level and Arabic-numbered ones (`3. Title`) nest under them; for a collection of numbered essays with Roman parts inside them, add `--toc-chapters arabic`. Check with `--toc-debug` first. EPUB inputs: pass `.epub` instead of `.txt`. Use absolute paths. Publish `OUTPUT.html` with the `Artifact` tool. (`--lang` is ignored in `--artifact` mode.)

**Then the PDF — same inputs, one more command** (details, corrections and checks in § PDF edition):

```bash
python3 /SKILL_BASE/scripts/build_pdf.py \
  /abs/path/ORIG.txt /abs/path/TRANS.txt \
  --author "Author Name" --work "<i>Work</i> (Year)" \
  --edition "the first edition of YEAR" \
  --lang de en --preview 3 \
  -o ~/Desktop/Title.pdf
```

Run it first with `--inspect` to see which paragraphs become headings (and at which level), notes and run-in titles; correct with `--level`, `--kind`, `--runin`; then render. Read `Title_preview/page-1.png` and one middle page. Deliver **both** files with `SendUserFile` and report the page count.

---

## § PDF edition (`scripts/build_pdf.py`)

The print counterpart of the reader, in the settled style: landscape US letter, Cormorant Garamond, original left / translation right with **paragraph starts aligned across page breaks**, a **table of contents at the front** (three heading levels; source page in brackets on the left, PDF page on the right), title block with an editorial footnote, running head with page numbers, the author's notes in smaller type where they occur, **page markers preserved inline as `[n]` in both columns**, **no line numbers**. How the engine works and every knob: `references/pdf-edition.md`.

**Inputs** (first is preferred): (1) `orig.txt trans.txt` — the aligned files the HTML was built from, through the same `build_pairs` (page numbers stripped and remembered, alignment verified); `.md` files go here too, normalised on load (§ Markdown sources: `#` depth → heading level, shown as `caps+md1` in `--inspect`); (2) a side-by-side `.html` made earlier (`DATA` array or `.pair`/`.row` markup); (3) a `pairs.json` from `--json-only`. Set `--lang L R` always — hyphenation and the contents labels depend on it.

**Workflow**

1. `--inspect` (or `--list` for every pair index): check that chapters, §§, `a)` subsections, notes and run-in titles were recognised and at which level. Defaults: unnumbered ALL-CAPS / `Kapitel` / keyword headings (Vorwort, Anhang…) and Roman numerals → level 1 (small caps); `§ N`, `N. Title`, `a. Title`, run-in titles → level 2 (italic); `a) Title`, `β) Title` → level 3 (roman). A numbered heading set in capitals is classified by its number and printed in title case (Roman numerals kept: `II. El Tiempo…`, never `Ii.`). Change a kind's level with `--level KIND=N`, force single pairs with `--kind IDX=h1|h2|h3|fn|text|runin`, name the pairs whose first sentence is a run-in section title with `--runin IDX,IDX` (the `Title. — …` form is found automatically). A heading OCR garbled beyond recognition (`y .` for `γ.`) is fixed upstream in `orig.txt` with `fix_orig.py`, or forced here.
2. Front matter from facts only: `--author`, `--work` (HTML allowed: `"<i>Psyche</i> (1846)"`), `--edition "the first edition of 1846"` (composes the page-1 footnote: language, text basis, bracket convention, notes — nothing you have not seen in the file or the message; `--footnote` to write it yourself), `--running-head` if the default `Surname, *Work*` is wrong, `--credit` only if given.
3. Render with `--preview 3`; read page 1 (title, contents, footnote) and a middle page (paragraphs aligned, dictionary hyphenation, markers and notes present). No `WARN` lines in the output; the layout page count and `pdfinfo` count must agree.
4. Deliver the PDF next to the HTML (same stem) with `SendUserFile`; report pages, contents entries, anything forced or left as found (OCR artifacts stay in the text — this step formats, it does not edit).

**Notes and page markers.** Paragraphs beginning `(1)`, `1)`, `1 Text`, `*`, `†`, `¹` are notes; after an `Anhang`/`Appendix`/`Notes` heading all paragraphs are notes until the next chapter (`--no-notes-appendix` to disable). A reference glued to a word by OCR (`zerfiele1).`) is raised to a superscript on both sides. Page markers come from the aligner (`page_after`, `page_mid`) and from markers already written in the text (`[12]`, `[p. 12]`, `[vii]`); the translation gets the marker at the same paragraph or the proportional word, as the HTML does. A pair holding several paragraphs is exploded one paragraph per row when both sides agree; otherwise a leading heading and trailing notes are split off.

**Book edition for print (`--facing`).** The same rows can be set as a bound book: portrait pages at a print trim (`--trim 6x9`, also `5.5x8.5`, `5x8`), the original on every verso (even) page and the translation on the facing recto, paragraph starts aligned across the spread exactly as in the two-column layout (one engine page = one spread), mirrored margins (`--margins IN,OUT,TOP,BOTTOM` in inches, default `0.875,0.625,0.9,0.75`, which meets the usual print-on-demand gutter rule for 300–500 pages), page numbers on the outside corner of every page with the author as verso running head and the work as recto running head, body type 16.5 px / 20 px leading (`--font-size`, `--line-height` to change). Front matter: p. 1 title page, p. 2 "Note on the text" (the `--footnote` text plus a sentence on the facing layout), contents from p. 3 as one bilingual column whose number is the verso page where the spread begins; a blank page is inserted so the text opens on a verso, and at the end so the count is even. Expect about 1.75× the landscape page count. Check page 1–8 previews (the text must start on an even page) and one middle spread.

```bash
python3 /SKILL_BASE/scripts/build_pdf.py ORIG.txt TRANS.txt --facing --trim 6x9 --author "…" --work "<i>…</i>" --lang es en --footnote "…" --preview 8 -o ~/Desktop/Title-6x9.pdf
```

**What the PDF step does not do.** Re-pair columns that drifted apart or split headings fused into paragraphs — that is `split_headings.py` / `fix_orig.py` work on the text files, followed by `--verify`. For an HTML-only source that needs such surgery: `--dump-rows rows.json`, edit, `--rows rows.json`.

**Requirements.** Google Chrome (found automatically on macOS, or `--chrome PATH`); Python 3 standard library; poppler (`pdfinfo`, `pdftoppm`) optional for the page-count check and previews. Fonts are bundled in `assets/fonts/`.

---

## Running on another machine — requirements and what stays local

The skill is self-contained: scripts, templates, fonts and agent definitions travel with it (`references/install.md` has the per-machine steps; `scripts/facing/doctor.py` checks them and prints the install commands). Nothing in it depends on a particular user's paths: Python is found by the `scripts/py` launcher (any Python 3 with numpy, Pillow, pypdf — a venv, the system one or Homebrew's), Chrome by `render.sh`/`build_pdf.py` (`CHROME=` overrides), the work folders live under the project's `_facing-pipeline/`.

**Local processing.** OCR is never sent to a cloud service: `bundle.py` reads the PDF's own text layer with poppler's `pdftotext`, and where a page has none it runs **Tesseract on this machine** (language from `book.json` `ocr.tesseract`, e.g. `frk` for Fraktur). Page images, line detection, the English typesetting (headless Chrome) and the PDF merge are local too. The only thing that leaves the machine is what Claude itself reads to translate: the line-numbered OCR text and the reading-size page views the scripts prepare. Keep it that way — do not replace the OCR step with a hosted API.

**Tools:** Python 3 (numpy, Pillow, pypdf), poppler (`pdftoppm`, `pdftotext`, `pdfinfo`), Tesseract with the languages the books need, Google Chrome or Chromium. macOS: `brew install poppler tesseract tesseract-lang` and Chrome; Linux: the apt equivalents (`doctor.py` prints them). Fonts: the clean-text edition uses the bundled Cormorant Garamond; the photocopy edition's English uses Hoefler Text where present (macOS) and falls back to Iowan Old Style / Palatino / Georgia — `fit.js` re-fits the type either way.

---

## Custom design path — `artifact-design`

```bash
python3 /SKILL_BASE/scripts/side_by_side_html.py \
  /abs/path/ORIG.txt /abs/path/TRANS.txt \
  --json-only -o /abs/path/pairs.json
```

The JSON is a list of `{"orig": "...", "trans": "...", "page_after": "..."}` objects. For the JS rendering skeleton (`fillCol`, `DATA.forEach`, page mark helpers), see the `_build_artifact_fragment` function in the script source.

---

## CLI reference

| Flag | Default | Notes |
|------|---------|-------|
| `--count` | — | Print paragraph counts and exit. Exits 0 on match, 1 on mismatch. |
| `--verify` | — | Anchor-based alignment check: counts + chapter headings + footnote markers. **Use this instead of `--count`** after translation. Exits 0 on match, 1 on any issue. |
| `--artifact` | off | Emit HTML fragment for Artifact tool |
| `--toc` | off | (Artifact mode only) Fixed left sidebar TOC with scroll-spy. Auto-detects Roman-numeral chapters, prefaces, § sections, Arabic-numeral sections (e.g., `1 The hedonism...`), and marginal run-in titles (`Heraklit. — …`; label taken from the translation column). A numbered heading is labelled from the translation when it starts with `Chapter N` / `Capítulo N` etc. |
| `--toc-debug` | — | Print detected TOC entries and exit. Use to verify what `--toc` would pick up before building. |
| `--toc-chapters` | `roman` | Which numbered headings are top-level in the TOC: `roman` (I., II.) or `arabic` (1., 2.); the other kind nests under them. Trailing `(N)` footnote markers are stripped from labels; ALL-CAPS labels are title-cased in the sidebar. |
| `--toc-kind IDX=tc0\|tc1\|tc2\|none` | — | (with `--toc`) force the TOC level of one pair, or drop it; repeatable. Parity of `build_pdf.py --kind IDX=h1\|h2`. |
| `--json-only` | off | Emit only the pairs JSON |
| `--hathitrust-prep` | off | One-command HathiTrust cleaning: strips markers, joins lines, merges page-boundary continuations, splits on structural markers, writes clean `orig.txt` via `-o`. Exits after writing. |
| `--book-ocr-prep` | off | One-command cleaning of a scanned-book OCR export (PDFgear/ABBYY/Acrobat/Tesseract): page numbers, running headers, signature marks, hyphenation, paragraph detection by short-line and marginal-title rules; writes `orig.txt` via `-o` and exits. |
| `--marginal-level tc0\|tc1\|tc2\|none` | `tc0` | (with `--toc`) sidebar level of run-in titles (`Heraklit. — …`); `tc2` nests them under the sections. |
| `--front-matter auto\|keep` | `auto` | Of several heading pairs before the first body paragraph (half-title, title page, title again) only the last enters the TOC. |
| `--md-dump DIR` | — | Markdown inputs: write the normalised `orig.txt` / `trans.txt` (exactly what the aligner sees) to DIR and exit. For inspection only — keep editing the `.md`. |
| `--no-propagate-markers` | off | Do not copy the original's inline `[n]` page markers into a translation that carries none (default: copied at the proportional word, which is what makes `--verify` pass for a translation without markers). |
| `--html-copy PATH` | — | With `--artifact`: also write a complete standalone HTML document (doctype, head, `<title>`) to PATH — use for a Desktop deliverable. |
| `--hathitrust` | off | Apply HathiTrust cleaning inline during build (same pipeline as `--hathitrust-prep`, but continues to HTML output instead of exiting). |
| `--detect-paragraphs` | off | Heuristic paragraph detection on `orig.txt` (flat-stream OCR). Does not modify input. |
| `--title` | from filename | Page title |
| `--left-label` | `"Original"` | Column header for source text |
| `--right-label` | `"Translation"` | Column header for translated text |
| `--lang` | `""` | BCP-47 `lang=` attribute (standalone mode only; ignored with `--artifact`) |
| `-o` | auto | Output path. Artifact mode defaults to `~/Desktop/<title-slug>.html`. |

**EPUB inputs:** pass `.epub` anywhere a `.txt` is accepted — auto-extracted via stdlib (no external deps).

**`build_pdf.py` reference**

| Flag | Notes |
|------|-------|
| `ORIG TRANS` / `FILE.html` / `pairs.json` | inputs (see § PDF edition) |
| `-o PATH` | output PDF (default `~/Desktop/<work slug>.pdf`) |
| `--author`, `--work`, `--title`, `--credit`, `--running-head` | title block and running head (HTML allowed in `--work` / `--running-head`) |
| `--edition TEXT` / `--footnote HTML` | editorial footnote on page 1: composed from `--edition`, or given verbatim (repeatable) |
| `--lang L R` | BCP-47 codes for hyphenation, contents labels (`Inhalt`/`Índice`…), footnote wording — always set |
| `--inspect`, `--list` | show the classification / every pair index, then exit |
| `--level KIND=N` | level of a heading kind: `caps kapitel keyword roman section arabic letterdot letterparen greek runin` |
| `--kind IDX=KIND` | force one pair: `h1 h2 h3 fn text runin` |
| `--runin IDX,IDX` | pairs whose first sentence is a run-in section title (italic + contents) |
| `--toc-chapters roman\|arabic` | which numbered headings are top-level (as in the HTML builder) |
| `--no-notes-appendix`, `--no-sup-refs` | keep appendix paragraphs as body text; leave `word1)` references alone |
| `--front-matter auto\|keep`, `--toc-skip-idx IDX,IDX` | front matter (leading heading rows) kept out of the contents by default; or name the pairs to leave out — no more `--dump-rows` editing for that |
| `--no-md-levels`, `--no-propagate-markers` | Markdown original: ignore the `#` depth of headings (kind defaults / `--level` apply); do not copy the original's inline page markers into a marker-less translation |
| `--marker-format "[{n}]"` | shape of page markers from the aligner |
| `--left-ratio 0.5`, `--paper letter\|a4` | column share of the original; paper |
| `--page-notes` | the author's notes as real footnotes at the foot of each column (not in the flow), cues renumbered per page; notes that do not fit continue overleaf. Cues are matched to notes by number (OCR-lost cues are added at the end of the preceding paragraph and reported) |
| `--break-bars`, `--note-marks FMT` | with `--margin-folios`: a thin red bar in the text where each source page begins, margin numbers in red without brackets (Trendelenburg style); with `--page-notes`: per-page note marks as `{n}` (default), `{n})`, or `*` (`*)`, `**)` …) |
| `--chapter-breaks` | landscape layout: each level-1 heading opens a new page; with `--page-notes`, notes still running from the previous chapter get pages of their own first |
| `--facing`, `--trim 6x9`, `--margins IN,OUT,TOP,BOTTOM` | book edition: portrait facing pages, original verso / translation recto, mirrored margins (inches) |
| `--font-size PX`, `--line-height PX` | body type (defaults 15.5/18; 16.5/20 with `--facing`) |
| `--dump-rows JSON` / `--rows JSON` | export the engine rows for hand edits / render from an edited file |
| `--preview N`, `--keep-html`, `--chrome PATH` | PNGs of the first N pages (poppler); keep the print HTML; Chrome binary |

**Helper scripts** (`scripts/`): `rtf_to_md.py BOOK.rtf [-o BOOK.md] [--list-headings]` (Word/RTF transcription → Markdown: heading styles → `#`, footnotes → `[^n]`, page numbers kept, fields/images/index dropped), `chunk_tools.py split|verify|status|assemble` (parallel sub-agent translation, see § Translation subagent); **Markdown fast lane** — `book_run.py BOOKDIR… [--init DIR] [--until STAGE] [--force STAGE] [--jobs N]` (queue driver: ocr → clean → translate → check → build, per-book `STATUS.md` and `run.log`), `translate_md.py SRC --source L --target R -o OUT [--provider lmstudio|openai|anthropic|mock] [--model] [--glossary] [--chunk-chars 9000] [--jobs N] [--resume]` (index-checked chunked translation; failed chunks halve, then are marked ⟪UNTRANSLATED⟫), `md_clean.py FILE.md [--side trans]` (OCR debris → `.refined.md` + flags), `align_check.py ORIG TRANS --emit DIR` (compact alignment report, `fixes_*.json`, `missing.json`, `source_issues.json`; exit 0 = one-to-one), `apply_missing.py TRANS missing.json` (inserts the filled translations at their anchors), `scan_page.py SRC N… -o DIR` (one book page of the scan as PNG), `md_edition.py ORIG TRANS --author --work --lang … -o PDF` (check → PDF → HTML in one command; `--check-only`, `--no-html`, `-- …` for build_pdf flags); `md_prep.py FILE.md [--side trans] [-o out.txt]` is the Markdown normaliser both builders call (run it alone to see the report or dump the text); `fix_orig.py FILE --regex PATTERN REPL` (or `--regex < list.json`) for pattern fixes such as heading levels; `pdf_bbox_paras.py PDF -o ORIG` rebuilds paragraphs from a justified PDF's line geometry (§ PDF with a text layer); `show_paras.py FILE START END` prints indexed paragraphs within a character budget (`.md` shown normalised; `--side trans` for a translation); `append_trans.py TRANS START --orig ORIG` appends a translated chunk with count/anchor checks; `fix_orig.py FILE` applies a JSON list of `[old, new]` corrections and aborts if any `old` is missing — it works on `trans.txt` too, which is how a reviewer's `old→new` list is applied; `append_pairs.py` appends source+translation together (pasted-text path).

**Review pass (optional, cheap, catches what the loop cannot).** After `--verify`, a read-only critic subagent given the two file paths and the glossary finds in ~5 minutes what a translator cannot see from inside the chunks: false friends (*actual*→present, *eventual*→possible, *casual*→fortuitous, *notorio*→evident), a glossary term that drifted between chunks (*iluminación* rendered both "illumination" and "elucidation"), doubled words, a heading rendered unconventionally. Ask for an `[old, new]` list and apply it with `fix_orig.py trans.txt`, then rebuild. A second critic on the built HTML/PDF (screenshots + page PNGs) is worth it for a book-length edition.

**Section-header detection** (artifact mode): paragraphs under 80 chars that are entirely uppercase render as centered dividers. Lowercase them to suppress.
