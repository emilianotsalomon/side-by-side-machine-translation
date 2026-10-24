# Facing edition of a scanned book — two layouts, one pipeline

For a scanned (or born-digital) printed book that does not yet have a translation, when the user asks for a "side by
side translation" of a PDF, typically "scope and plan out … give only output pdf, keep original pagination, preserve
stylistic choices". Deliverable: ONE landscape PDF, in the layout the user chooses **when the PDF comes in** (ask with
one AskUserQuestion unless they named it; describe both in plain words):
- **Photocopy edition** — `"layout": "facing"` — like the *Hegel, Encyclopaedia 1817*: one spread per original page,
  the original page on the left (vector-crisp, cleaned), the English typeset on the right with every block aligned
  to its original line; folios, signatures, footnotes, emphasis and ornaments as printed; PDF bookmarks.
- **Clean-text edition** — `"layout": "retype"` — like the *Exner, Psychologie der Hegelschen Schule* ("Trendelenburg
  style"): both columns freshly typeset, original left / English right, paragraph rows aligned; the original
  pagination marked at the exact word where each page begins (number in the outer margin, thin red bar in the text);
  footnotes at the page foot with the book's own marks; chapters on new pages; a contents page. No scan reproduced.
No HTML reader unless asked. Everything up to the review is the same pipeline; the clean-text layout adds one file per
page (the corrected original) and a different build (§ Clean-text edition).

Scripts: `SKILL_BASE/scripts/facing/` — `new_book.py` copies them (and the PDF engine) into the book's folder.
Templates: `SKILL_BASE/templates/facing/`. Lean agent definitions: `SKILL_BASE/agents/` (§ Agents). **Python: always
through the launcher `scripts/py`** (`scripts/py bundle.py work s020`): it finds a Python 3 with numpy, Pillow and
pypdf on whatever machine this runs (a venv, `/usr/bin/python3`, Homebrew…) — never write a Python path into a brief
or a command. `scripts/py doctor.py` checks every tool and prints the install commands. **All scan processing is
local**: page images (poppler), line detection (numpy), OCR (the PDF's text layer via `pdftotext`, else Tesseract on
this machine), typesetting (headless Chrome, found by `render.sh`; `CHROME=` overrides), merge (pypdf). Only the OCR
lines and page views that Claude reads to translate leave the machine. Do not replace the OCR with a hosted service.

## Standing choices (the user's defaults — do not re-ask them)
Scan left, English right, one spread per original page · drop non-text pages (library notices, blanks, publisher ads,
stamped duplicate title pages) · quotations from English-language authors restored from the original English where
found, others translated fresh with the standard terminology of the field (Kant/Hegel-standard terms etc.) · proper
names modernised in the English only · Latin/Greek kept as printed + [English gloss] where helpful · American
spelling · running heads, folios, signatures and misprints kept as printed · straight through, no pilot · PDF
bookmarks. The layout (photocopy / clean text, above) is the one question asked FIRST, when the PDF arrives. Then
ask only what is genuinely new for this book (e.g. a missing page to splice from another copy, a policy the glossary
cannot settle), in ONE further AskUserQuestion during scoping.

## Token rules — measured on the October 2026 editions; they decide the cost
1. **Pass `effort` on every Agent call** (this skill asks for it explicitly): translators `medium`, reviewers
   `medium` (`high` for the hardest texts, e.g. Hegel). Without it every subagent inherits the session's effort:
   Bolzano ran at `max` and Hegel at `xhigh`, and their Sonnet translators spent 5–12k thinking tokens and 8–13 calls
   per page with extra zooms — 3.3M cache reads + 26k output per page against 0.12M + 1.5k per page for the
   `medium` Dilthey batches two days earlier. Bolzano's job came to ≈ 170M input-equivalent tokens for 228 pages
   (Hegel 1817: ≈ 90M for 302); the same work under these rules is ≈ 30M.
2. **One bundle call per pair of pages.** `bundle.py` gives a page's whole input (line-numbered OCR with paragraph,
   centring and letter-spacing marks, rules, folio/signature expectations, neighbour edges) plus two reading-size
   views. Old procedure: zoom image + 3 crops + ad-hoc PIL zooms + OCR dump + Write ≈ 13 calls/page; bundle
   procedure: ≈ 2 calls/page. Blind test, 4 Bolzano pages: Sonnet-medium, Sonnet-high and Opus-medium all needed
   7–11 calls in total and ≈ 55k input-equivalent tokens per page; none made a serious sense error; Opus-medium had
   near-perfect emphasis and markup.
3. **Keep every agent's peak context under ~180k.** Above ~200k Claude Code trims old tool results, which breaks the
   prompt cache: each trim re-writes the whole context (one Bolzano reviewer re-wrote 3.6M tokens in 23 trims; 73% of
   a translator's cache writes were such rewrites). Translators ≤ 12 pages, reviewers ≤ 25 pages per agent.
4. **After a usage-limit stop, start fresh agents on the missing pages** (`status.py`), do not SendMessage the old
   ones: resuming re-writes an agent's whole stale context (≈ 300k each, ×10 agents per stop in Bolzano); a fresh
   agent costs its ≈ 50k setup.
5. **Translators never build, render or look at PDFs**; the orchestrator runs `make.py` once over the whole book
   (≈ 15 s) and sends overflow/drift pages to the reviewers.
6. **Keep the orchestrator's own context lean** — it is re-read on every wake-up (each agent completion, each user
   message) and re-written after every limit pause: Bolzano's main context reached 518k. So: use these scripts
   instead of reading the previous book's; scope from one contact-sheet montage, not page-by-page PDF reads; write
   ≤ 6 model pages yourself (one per page type); never cat whole scripts or long outputs into context.
7. **Report true cost at the end** with `usage.py` (the "tokens" an Agent result reports is only its final context).

## Phases
| phase | who | what | budget |
|---|---|---|---|
| 0 scope | you | pdfinfo, page sizes, `pdffonts`/`pdfimages -list` (text layer? source type), one montage of ~24 thumbnails (`pdftoppm -r 12` + PIL grid), 3–4 pages at reading size; find printed-page offset, drop list, features (footnotes, signatures, catchwords, Fraktur/Antiqua, Greek, tables, plates, missing/duplicated pages — compare OCR of neighbours); plan + questions | ≤ 15 calls |
| 1 setup | you | folder, copy scripts, `book.json`, `prep.py`, `lines.py`, `bundle.py` smoke test on 2 pages | ≤ 10 calls |
| 2 standard | you (or one Opus agent) | GLOSSARY.md (an Opus research agent for period translations/standard terms if the field has them), ≤ 6 model pages, AGENT.md + REVIEW.md from the templates, `extra.css`, one `make.py` of the model pages | ≤ 25 calls |
| 3 translate | agents | batches of ≤ 12 pages, ≤ 20 at once, `effort: medium` | ≈ 2 calls/page |
| 4 check | you | `make.py --checks-only` (check, seams, folios), then `make.py` for the fit report | 2–3 calls |
| 5 review | agents | ranges of ≤ 25 pages, start each as soon as its batches land, `effort: medium` (`high` for very hard texts) | ≈ 1.5 calls/page |
| 6 finish | you | `finalfix.py` (book-wide term fixes), `catchwords.py`, `make.py`, look at 2 spreads, `usage.py`, deliver | ≤ 10 calls |

### 0–1. Scope and set up
```bash
SKILL_BASE/scripts/facing/py SKILL_BASE/scripts/facing/new_book.py <slug> "<source.pdf>" \
    --layout facing|retype --kind ia|google|hathi|plain|images --lang frk|deu|lat|fra|ita|spa \
    [--first N --last N] [--title "…"] [--author "…"] [--out "<deliverable>.pdf"] [--prep [--flat]]
# → ~/Desktop/claude-folder/_facing-pipeline/<slug>/{scripts,engine,work}: scripts copied, book.json with the layout,
#   briefs from the templates (the clean-text section kept only for layout retype), DROP, agents installed, doctor run.
#   --root DIR for another place (persistent — never the session scratchpad, which gets wiped).
B=~/Desktop/claude-folder/_facing-pipeline/<slug>; cd $B          # then edit work/book.json (folio ranges, drop list…)
scripts/py prep.py work ia|google|hathi|plain|images [--flat]       # unless --prep did it
scripts/py lines.py work > work/lines.log                           # red-numbered zoom/ PNGs + lines/*.json
scripts/py bundle.py work s020 s021                                 # smoke test: OCR lines match the red numbers?
```
Source types: **ia** (Internet Archive MRC: `fzImg0` background), **google** (Google Books: `/GS1` image layers,
`/Wm` stamp), **hathi** (HathiTrust: `/Ix…`/`/Jx…` image at an offset, `/CBJ` stamp form — sets `ocr.align`),
**plain** (born-digital or clean), **images** (camera scans in `work/raw/`: whitened, deskewed, framed). `--flat`
for dark or unevenly lit scans. Fraktur without a text layer: set `"ocr": {"tesseract": "frk"}` (or `script/Fraktur`);
Antiqua: `deu`, `ita`, `fra`, `lat`, `spa` …
`book.json` holds everything book-specific that used to be patched into the scripts: layout, page range, geometry,
folio format and scan→printed offsets (several ranges, roman numerals, a `"prefix": "I."` for multi-part volumes),
printer's signatures, OCR source and Tesseract language, fit limits, bookmarks, metadata, output path (`~` allowed). Geometry: `sc` = pt per scan px so the scan fills the left half (a 1500-px-tall
scan on a 760-pt sheet → 0.48); `tw` ≈ the printed text width in pt; tall quartos need a wider sheet (Dilthey:
1200×810, sc 0.52, tw 405). Drop list: `work/DROP` (`s001 s003 …`).

### 2. Glossary, model pages, briefs
Model pages (≤ 6): the page types that recur — a plain body page, a page with footnotes (begun / continued), an
opening with headings, a page with a signature, a special layout (formula, verse, table, contents). Write them with the
same bundle procedure the translators use, then `make.py` on just those pages (`build.py work out.html A B` +
`render.sh`) and look at one spread. Fill `AGENT.md` and `REVIEW.md` from the templates (keep their Procedure
sections verbatim); settle every policy in `GLOSSARY.md` now — each one left open has cost a book-wide repair pass.
Write `work/batches.txt` (`B01 006 017` … `R1 006 030` …).

### 3. Translators
```
Agent(subagent_type="facing-translator" if installed else "general-purpose", model="opus", effort="medium",
      run_in_background=true, description="Translate B07 s078–s089",
      prompt="You are translator B07 … W = <abs path>/work. Read W/AGENT.md and follow it exactly. Your pages: s078–s089.
              Notes: W/notes/b07.md.")
```
Model: **Opus at medium** by default (best emphasis and markup in the blind test, fewest review fixes); Sonnet at
medium is the cheaper option for plain modern prose. Never omit `effort`. Up to 20 agents run at once; queue the rest.
Include display pages (title, contents, part titles) in a batch only with a model page for them.

### 4–5. Checks and review
`make.py work --checks-only` → `check.py` (anchors, tags, length ratio), `seams.py` (missing pages, words duplicated
across joins), `folios.py` (folio and signatures against book.json — translators write scan numbers, swap recto/verso
heads and "correct" misprints). Then `make.py work` for the fit report: overflow is never acceptable (fix anchors,
never cut text), drift > 12 and type-size changes are listed for the reviewers. Reviewers: `facing-reviewer`
(or general-purpose), `model="opus"`, `effort="medium"`, ranges ≤ 25 pages aligned with batch ends so seams are
inside a range, started as soon as their batches exist. They read text first (`bundle.py --en --no-views`) and views
only where needed. Expect ~1 sense error per 2–4 pages from translators — the review is not optional.

### 6. Finish
`finalfix.py` with `work/finalfix.json` for book-wide term decisions made late (text nodes only, anchors safe);
`catchwords.py --apply` (catchword = next page's first English word; photocopy layout); `make.py work` → the
deliverable (path in book.json; it builds whichever layout book.json names); look at two spreads at 60 dpi;
`usage.py <session> --pages N` (run from the book or project folder) and give the true cost in the final message.

## Clean-text edition (`"layout": "retype"` — Exner / Trendelenburg style)
Chosen at the first question (or when the user asks for the style of the Trendelenburg *Logische Untersuchungen* or
the Exner edition, a "retypeset" or "typeset original", "clean text", a text without the scan). Both columns are
typeset (original left, English right, landscape letter, paragraph rows aligned); the original pagination is marked
at the exact word where each page begins — the number in the outer margin, a thin red bar in the text (both
columns); the author's footnotes stand at the foot of the page with the book's own kind of mark (`*)` or `1)`,
counted per page, or the printed numbers kept); chapter titles are headings and every chapter opens a new page; a
contents page with original and English headings; PDF bookmarks from the contents. The scan is not reproduced.
Everything up to the review is the same pipeline (prep, lines, bundle, glossary, translators, reviewers) with one
addition: translators also write `W/orig/sPPP.html`, the corrected original in the same blocks as the English
(templates/facing/AGENT.md § Retypeset editions — `new_book.py --layout retype` keeps that section in the brief).
Because each page's text starts exactly at the page break, the page markers fall at the right word in both columns.
Settings in book.json (written by `new_book.py`, then filled in):
```json
"retype": {"levels": {"h1": 1, "h2": 2, "h3": 2, "h4": 3}, "note_marks": "*", "lang": ["de", "en"],
           "author": "Franz Exner", "work": "<i>Die Psychologie der Hegelschen Schule</i> (1842–1844)",
           "edition": "the first edition (Leipzig: Fleischer, Heft I 1842, Heft II 1844)",
           "footnote": "<optional: the page-1 note written out instead of composing it from edition>",
           "keep_note_numbers": false, "build_flags": ["--kind", "0=orn", "--kind", "30=ver"]}
```
`keep_note_numbers: true` keeps the book's own continuous note numbers (`22)`) instead of counting per page
(Brentano); `build_flags` are passed to build_pdf.py on every build (so no `make_final.sh` is needed); folio ranges
may carry `"prefix": "I."` so the margin numbers read `I.23` / `II.5` for a two-part volume (Exner). Display blocks
the translators may use in both files (AGENT.md lists them): `ctr`/`ctrp` centred title lines (`ctrp` opens a new
page), `epi`/`epa` epigraph and attribution, `syn` synopsis line, `ver` verse, `quo` block quotation, `sep` a printed
section rule. An unmatched `1)` in the running text is an enumeration and stays (the engine no longer deletes it).
Build: `make.py work --checks-only` runs check, seams and `retype.py --check` (orig and English have the same block
structure on every page; every note cue has its note); `make.py work` then runs `retype.py` → `work/retype/orig.md` +
`trans.md` → `engine/scripts/build_pdf.py` with `--chapter-breaks --page-notes --margin-folios --break-bars
--note-marks …` (anything after `--` is passed on too). A pilot: `retype.py work OUT.pdf --pages 16-22,69-72` (plain
or `s016-s022` numbers). Read the preview pages it writes (title/contents, a chapter opening, a page with notes).
Cost: about 1.5× the
translation output (two files per page); reviewers see both texts in `bundle.py --en`. Paragraphs running over a page
are rejoined; folios, signatures, catchwords, rules and ornaments are dropped (the margin numbers replace them);
printed line breaks inside a block (schemata, verse, `<br>`) are marked with " | " (kept on the line before, never opening a line). Tested on Bolzano pp. 15–21 and 68–71 (Opus at medium wrote the
German transcription of 10 pages in 31 calls, ~3 minutes): part title on a new page, margin numbers and bars at the
exact breaks, the `*)` note continued across two pages set whole at the foot, numbered points kept as body text.
Where a translator completed a clause on the earlier page, the English bar sits a few words from the German one —
that is the translation, not an error.

## Corpus and reader (the team's knowledge base)
`corpus.py book BOOKDIR -o CORPUS --title … --author … --year … --lang de` writes ONE Markdown file per edition from the
page files: a YAML header (author, title, languages, where the original text comes from, review status), then the
text with `[p. N]` at every printed page start, the original in quoted blocks (`> …`), the English in plain paragraphs
(paragraph pairs for clean-text editions, page pairs with the uncorrected OCR for photocopy editions). `corpus.py pdf
FILE.pdf …` recovers the English (and, with `--both`, the original) from an edition whose page files were not kept.
`corpus.py text FILE …` adds an ORIGINAL with no translation (PDF with a text layer, EPUB, Markdown or plain OCR text; `--ocr deu|frk` runs Tesseract locally on scan pages without text); `corpus.py chunks DIR …` imports a chunk_tools translation (cNN.src.md + cNN.en.md). Only public-domain texts and the team's own translations belong in a shared corpus — never a copyrighted modern edition. `corpus.py index CORPUS` writes the README table. `reader.py CORPUS DOCS` turns the corpus into a static site (one
page per edition, one card per printed page, original left / English right, find-on-page) for GitHub Pages. The
corpus files are generated: corrections go into the page files, then re-export (the team's `export_all.sh`).

## Agents (lean definitions)
`agents/facing-translator.md` and `agents/facing-reviewer.md` restrict subagents to Read/Write/Edit/Bash: a
general-purpose subagent carries ≈ 42k tokens of tool schemas and system prompt into every call; these carry far
less. They take effect only in a session started after they are copied to `~/.claude/agents/` (check with
`ls ~/.claude/agents/facing-*.md`); until then use general-purpose with the same prompts.

## Gotchas collected from fourteen editions
- Setup: the book folder must be persistent (`_facing-pipeline/<slug>`, not the scratchpad); every engine patch made
  inside a book folder must go back into the skill (Exner's and Brentano's `engine/` copies carried fixes for a day
  that the next book then missed) — edit `SKILL_BASE/scripts` and re-copy, never only `BOOK/engine`.
- Scans: check for missing AND duplicated pages before planning (compare the first 600 OCR characters of neighbours);
  missing pages can be spliced from another copy (scale the text block to match). Library stamps stay on the left;
  ignore them in the English.
- Lines: red 1 is the first text line; the folio is never numbered (`lines.py` stores it as `folio`); a catchword or
  signature below a >4-line gap ends the text block for type growth; very short last lines need the low row threshold.
- Anchors: anchors must increase; display pages anchor by `data-at` (blue ruler); figures cut from the scan are
  `<p class="fig" data-at="T"><span class="device" data-box="L,T,R,B"></span></p>` or `orn.py` images.
- Type: Hoefler Text lacks U+2212 (book.css maps it to Times); inline formulas in `span.fx` with U+2009 thin spaces;
  lining numerals (old-style 1 reads as I next to vol./§ numbers).
- Translators: "correct" running heads, folios and misprints (forbid it); trim text to avoid overflow (reviewers
  restore it); split numbered headings three different ways (fix the rule in AGENT.md with a model page); drift
  between batches on recurring terms (list them in the glossary beforehand); normalise Greek away from the print
  (rule: non-word misprint → standard text, real variant → keep); override correct `‹…›` spacing hints (the brief
  now says they are reliable).
- Reviewers sharing a folder: helper scripts named `R<n>_*.py`, edits grep-verified; reviewers have converted the
  print's "§" references to "p." — say which the print uses.
- Seams: a "completed clause" on one page plus the same words on the next page is the commonest join error —
  `seams.py` catches most; reviewers check the rest.
- Usage limits: everything on disk survives; `status.py` gives the restart lists; usage-limit pauses also expire
  the prompt cache (5 minutes), so a smaller context is cheaper to restart.
- File size: vector-merged scans keep 1-bit/JBIG2 sources tiny; `compress_identical_objects` after merging.
