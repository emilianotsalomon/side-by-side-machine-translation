# The PDF edition: what `build_pdf.py` produces, how, and how to correct it

## The look (settled September 2026)

Landscape US letter, Cormorant Garamond Medium 15.5/18 px (≈ 11.6/13.5 pt), justified and
hyphenated with the Mac's dictionaries for the two `--lang` codes. Page 1 carries the title block
(author; work with a footnote mark) and the beginning of the **table of contents**; the contents
continue on further front pages as needed. The text starts on a fresh page. Original left,
translation right, **paragraph starts aligned**, a paragraph split across pages when needed (no
widow or orphan lines). Every page after the first has a running head (`Surname, *Work*` … page
number) over a rule. **No line numbers, no revision line.**

Three heading levels, all kept whole and kept with the paragraph that follows:

| level | set as | default kinds |
|---|---|---|
| h1 | small caps; a `LABEL Title` heading (`ZWEITES KAPITEL Zweiter Teil…`, `EINLEITUNG Die gegenwärtige…`) becomes two lines, label over title | `caps`, `kapitel`, `keyword` (Vorwort, Einleitung, Anhang, Appendix…), `roman` |
| h2 | italic | `section` (§ N), `arabic` (N. Title), `letterdot` (a. Title), `runin` |
| h3 | roman | `letterparen` (a) Title), `greek` (β. Title) |

ALL-CAPS headings are set in mixed case (first letters capitalised, small function words lower)
because small caps of capitals just print as capitals. Change a kind's level with
`--level KIND=N` (Carus 1846: `--level letterdot=2 --level arabic=3 --level greek=3`); force a
single pair with `--kind IDX=h1|h2|h3|fn|text|runin`. `--inspect` prints exactly what was
recognised, with pair indexes, before anything is rendered.

**Contents**: two columns like the text — original heading left with the source page in square
brackets (the last page marker seen before the heading), translated heading right with the page
in this PDF. Indented by level. Run-in titles appear as level 2.

**Page markers**: everything the aligner found (`page_after`, `page_mid` — see § Page number
formats in SKILL.md) is printed inline as `[n]` in *both* columns: at the start of the paragraph
that begins the page, or inside the paragraph at the word where the page turns (the translation
gets it at the proportional word, as the HTML does). Markers already written in the text
(`[12]`, `[p. 12]`, `[vii]`) are kept as they are. Change the shape with `--marker-format "<{n}>"`.

**The author's notes** — paragraphs beginning `(1)`, `1)`, `1 Text`, `*`, `**`, `†`, `¹` — are
set in smaller type (12.6/15 px) below the paragraph they follow, with a small gap before a
note or group of notes; a bare number (`1 Text`) is raised to a superscript. After an
`Anhang` / `Anmerkungen` / `Appendix` / `Notes` heading every paragraph counts as a note until the
next h1 (`--no-notes-appendix` turns that off — Klages 1921 keeps all his notes in the Anhang).
A note reference glued to a word by OCR (`zerfiele1).`) is raised to `zerfiele¹⁾.` on both sides
(`--no-sup-refs` to leave it). Editorial footnotes of the *edition* (text basis, bracket
convention) go on page 1 under the contents: pass `--edition "the first edition of 1846"` and one
is composed from facts only (language, edition, whether markers and notes exist), or write it
yourself with `--footnote`. Never state an edition you have not seen in the file or the message.

**Run-in section titles** (Klages: `Einleitendes. Seit rund einem Jahrhundert …`; Ortega:
`Heraklit. — …`): the `Title. — ` form is recognised automatically; for the bare form pass the pair
indexes, `--runin 1,8,11`. The lead is set in italic in both columns and listed in the contents.

## Inputs

1. `orig.txt trans.txt` (or `.epub`) — **preferred**: the same aligned files the HTML was built
   from, through the same `build_pairs` (page markers stripped and remembered, alignment verified;
   verification problems are printed and the PDF still shows them side by side).
2. `Title.html` — a side-by-side reader made earlier: the `DATA` array (compact or object form),
   or `.pair` / `.row` markup. Chapter rows a reader marked as such are honoured; a chapter heading
   the reader glued to its first paragraph is split at the first sentence end.
3. `pairs.json` — a list of `{"orig","trans", "page_after"?, "page_mid"?, "mid_offset"?}` (what
   `side_by_side_html.py --json-only` writes).

A pair whose text holds several paragraphs (`\n`) is exploded into one pair per paragraph when both
sides have the same number; otherwise a leading heading and trailing notes are split off and the
rest stays one cell. A heading with no counterpart in the translation (the translator merged it
into the next paragraph) is split off the translation at the first sentence end.

### Markdown inputs (added 19 September 2026)

`ORIG.md TRANS.md` is input (1) with one extra step done for you: `scripts/md_prep.py` normalises
each file on load (see § Markdown sources in SKILL.md) and prints a report. What reaches the engine:
`#` headings as standalone paragraphs carrying `md_level` = the `#` depth, which becomes the
heading level (h1/h2/h3) unless `--no-md-levels` or an explicit `--level KIND=N` for that kind;
`[^n]: text` notes as `(n) text` (set in note type); the original's standalone `[n]` blocks as
page_after / page_mid; the translation's own `**[n]**` page blocks dropped, and the original's
inline markers copied into the translation at the proportional word (`--no-propagate-markers`).
`--inspect` shows `caps+md1` / `caps+md2` in the pattern column for these headings. Corrections
belong in the `.md` (fix_orig.py works on it; `old` must match the raw Markdown) — the dumped
`--md-dump` copies are for reading only. First case: Llosa, *La filosofía humanista de Mariano
Iberico* (1952), OCR `.md` + Qwen translation `.md`.

**Front matter and contents (September 2026).** With `--front-matter auto` (default) several heading
rows before the first body paragraph — half-title, title page, the title again — are set as headings
but only the last one enters the contents; `--toc-skip-idx 0,1` names pairs to leave out explicitly.
`md_edition.py` is the one-command driver for two Markdown files (align_check → build_pdf → HTML).

## The engine (assets/pdf_template.html)

Browsers cannot keep two columns in step across pages, so the template typesets in JS after the
fonts load: each row (a paragraph pair, a heading pair, a note pair) is measured in two hidden boxes
of the column widths; every line's text is read back through `Range` rects (inline `<i>`, `<sup>`,
`<span class="pg">` preserved, Chrome's hyphens restored); rows are paginated in pixel units —
body lines 18 px, note lines 15 px, snapped back to the 18 px grid after a note — with widow/orphan
control, headings kept whole and with at least two lines of the next row, a heading's leading
blank line dropped at the top of a page. Body pages are laid out first; the front matter (title
block, contents with the now-known page numbers, editorial footnote) is built afterwards, and the
body pages renumbered by the number of front pages (iterated until stable). Chrome then prints the
fixed-size `.page` divs. The console line `STATS {…}` is read back by the script; any `WARN` line
(non-integer line height, empty line, line-count mismatch) points at odd input — an HTML tag in the
text, a stray `<br>` — and is printed.

Knobs: `--left-ratio 0.46` when the original runs much shorter than the translation (Latin);
`--paper a4`; `--dump-rows rows.json` → edit → `--rows rows.json` when a correction cannot be
expressed with `--kind` (for instance re-pairing paragraphs by hand); `--keep-html` to inspect the
print HTML; `--preview N` writes PNGs of the first N pages (needs poppler).

## Checks before delivering

Read page 1 and one middle page (`--preview 3`, or read the PDF). Contents page numbers can be
spot-checked with `pdftotext -f N -l N`. Both columns must start each paragraph at the same
height; hyphenation must be dictionary-style (`Erscheinun-gen`, never `Erscheinung-en`); no `WARN`
in the output. The script prints the layout statistics (pages, front-matter pages, contents
entries) and the PDF page count from `pdfinfo` when poppler is installed.

## Cases met so far (September 2026)

- **Carus, Psyche 1846** (522 pairs, `[n]` markers inline in both columns, notes as `1 Text`
  paragraphs, often at the end of a multi-paragraph pair): `--level letterdot=2 --level arabic=3
  --level greek=3`; OCR turned `γ.` into `y .` — force with `--kind IDX=h3`. 513 pages.
- **Klages, Vom Wesen des Bewußtseins 1921** (`.pair` markup, no page numbers in the file, run-in
  titles, all notes in the Anhang, references like `zerfiele1)`): `--runin` with 22 indexes,
  `--kind 29=h2` for one standalone title. 123 pages.
- **Heidegger, GA 28** (a rough pairing: ~60 headings fused into paragraphs on one or both sides,
  columns one paragraph out of step in stretches): this is *upstream* work — fix `orig.txt` /
  `trans.txt` with `split_headings.py` and `fix_orig.py` and re-verify — not something the PDF step
  should repair. When only the HTML exists, `--dump-rows`, edit, `--rows`.
