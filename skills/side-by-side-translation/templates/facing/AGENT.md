# Translator brief — {{TITLE}} ({{PLACE}} {{YEAR}}), {{LANGUAGE}} → English
<!-- Template from the side-by-side-translation skill. Fill every {{…}}; keep the Procedure and Page-boundary
     sections verbatim (they are what keeps a batch cheap and the seams clean); replace the markup list with this
     book's classes (copy them from the model pages you wrote). Aim for <= 7 KB. -->

You translate the scan pages in your list into **one HTML fragment per page**, `W/en/sPPP.html`. A build script
places each English page beside its scan (scan left, English right, one spread per original page) and aligns every
English block to the height of the original line it is anchored to. `W` = `{{WORK}}`; scripts are in `W/../scripts/`.
Scan number PPP = PDF page; {{PRINTED_PAGE_RULE}}.

## Procedure — two pages at a time (keep to it: it is what keeps a batch fast and cheap)
1. Once: `cd W && cat GLOSSARY.md en/{{MODEL1}}.html en/{{MODEL2}}.html en/{{MODEL3}}.html en/{{MODEL4}}.html`
   ({{MODEL_DESCRIPTIONS}}). The glossary is binding; copy the model pages' markup exactly.
2. For each pair: `cd W/.. && scripts/py bundle.py work sAAA sBBB` prints, per page, the expected
   folio and signature, the last line of the previous page and the first of the next (and their English if already
   written), then the OCR **line by line, numbered exactly like the red numbers** (`L12`), with `¶` indented line
   (new paragraph), `⏎` line ends short (paragraph end), `c` centred, `‹…›` letter-spaced, and printed rules
   (`rule y=1029 after L26`). It writes the page images ("views": red line numbers left, blue scan-y ruler right).
   **Read all views of the pair in ONE message.**
3. Write both pages — two Write calls in ONE message, together with the bundle call for the next pair.
The OCR is good but not perfect ({{OCR_QUIRKS}}): the view is the authority for every doubtful word.
`‹…›` marks are measured letter-spacing and are right far more often than they look: set them as emphasis unless
the view plainly shows normal spacing; also look for spaced words the OCR split oddly.
Do not: make extra crops or zooms (views are at reading size; only for a truly illegible word:
`scripts/py crop.py work sPPP FIRST LAST`), re-read pages you have written, build or render PDFs, read
other briefs or memory files. Think briefly about genuinely hard constructions; do not draft a page in your head
before writing it — write it directly.

## Markup of `W/en/sPPP.html`
A flat sequence of blocks. Each block that starts on a new line of the original gets `data-l="N"` = the line number
where it starts (`7.5` = between lines 7 and 8). Anchors increase down the page. Elements without a line number
(signatures, rules, ornaments) are anchored with `data-at="Y"` = the blue-ruler y of their TOP (the bundle prints
rule y's). Write only the pages in your list; never overwrite other files in `en/`.
- Folio: `<p class="rh">{{FOLIO_EXAMPLE}}</p>` — NO data-l (placed automatically); exactly what the bundle expects;
  none where it says "none printed". Never "correct" a folio the print gets wrong — keep the misprint and note it.
- Paragraph continuing from the previous page: `<p data-l="1">`; new indented paragraph: `<p class="par" data-l="N">`.
{{BOOK_MARKUP}}
- Emphasis: letter-spaced type (Sperrdruck){{EMPH_EXTRA}} → `<em>…</em>` exactly where printed. Never `<strong>`.
- Footnotes: mark `<sup>{{NOTE_MARK}}</sup>` in the text; at the foot `<hr class="fn" data-at="Y">` then
  `<p class="note" data-l="N">…</p>`; a note continued from the previous page: `<p class="note cont" data-l="N">` (no
  mark). Notes running over a page break end and resume exactly like body text.
- Printer's signatures (the bundle says when one is expected): {{SIG_MARKUP}}. Keep them exactly as printed.
- Catchword at the foot: `<p class="cw" data-l="N">…</p>` (its text is set by script later — any word will do).
- Quotes: English “…” (inner ‘…’); {{QUOTE_RULES}} A page that begins inside a quotation starts with “.
  Apostrophe ’. Dashes as printed (—). Escape & as `&amp;`. No `<!-- fs=… -->` on text pages.
- Ignore stamps, pencil marks, show-through, specks.

## Translation
- Faithful, complete, precise English for a scholarly reader; no omissions, additions, paraphrase or condensing.
  Keep long periods, rhetorical questions, parentheses and dashes where English can bear them. GLOSSARY.md is binding.
{{BOOK_TRANSLATION_RULES}}
- Grammar traps: reported speech (subjunctive = the author reports, not asserts), case endings for subject/object,
  negations ({{NEGATIONS}}), particles ({{PARTICLES}}), elliptical constructions (supply the omitted noun/verb).

## Page boundaries
Each English page holds exactly the content of its original page. A sentence running over the break ends the English
page at the corresponding point; a word hyphenated across the break is finished on the page where it starts; if word
order puts the verb on the next page, complete the clause where most of it stands and continue from there on the next
page — never duplicate or drop words. When the neighbour's English exists (the bundle shows its edge), join exactly
onto it. English longer or shorter than the original is normal; never condense to make it fit.

## Retypeset editions only (book.json has a "retype" section; delete this section otherwise)
For every page also write `W/orig/sPPP.html`: the original text, transcribed exactly, with **the same blocks in the
same order and with the same classes as your English page** (folio, signature and catchword blocks may be copied as
they are — they are dropped from the retypeset edition). Original orthography as printed ({{ORTHOGRAPHY}}); long ſ →
s; line-end hyphenation joined; letter-spaced words → `<em>`; quotation marks as the language sets them („…“ / «…»),
NOT repeated at every line; footnote cues `<sup>…</sup>` at the same points as in the English; obvious misprints
corrected only where the glossary says so. Write the two files of a page in the same message. The bundle's OCR lines
are your draft: correct them against the views word by word.
Display blocks (same class in both files; the build sets them apart from the running text): `<p class="ctr">` a
centred line or lines of a title page (`ctrp` = the same, opening a new page), `<p class="epi">` an epigraph and
`<p class="epa">` its attribution, `<p class="syn">` a synopsis / outline line with hanging indent, `<p class="ver">`
verse (lines separated by " / "), `<p class="quo">` a set-off block quotation, `<p class="sep">` a printed section
rule. Footnote cues `<sup>21)</sup>` keep the PRINTED number (never renumber); the note itself begins with the same
number as plain text, `<p class="note" data-l="N">21) …</p>`; a further paragraph of the same note `<p class="note np">`.

## Finish
`cd W/.. && scripts/py check.py work FIRST LAST` (silent = fine; it flags non-monotonic anchors,
unbalanced tags, unescaped &, and an EN/original length ratio outside 0.75–1.35 — look for an omission or a wrong
page split). Do not build or render. Notes for the reviewer (doubtful readings, misprints kept, term decisions not in
the glossary) → `W/notes/<your id>.md`. Final reply: one short paragraph — pages written, check result, doubts.
If you were restarted, write only the pages still missing.
