# Reviewer brief — {{TITLE}} ({{LANGUAGE}} → English facing edition)
<!-- Template from the side-by-side-translation skill. Fill the {{…}}; keep the procedure. -->

`W` = `{{WORK}}`. First, in ONE call: `cd W && cat AGENT.md GLOSSARY.md notes/*.md` (markup and translation rules,
binding policies, the translators' doubts).

## Procedure — two pages at a time
1. `cd W/.. && scripts/py bundle.py work sAAA sBBB --en --no-views` prints, per page, the original OCR
   line by line (`‹…›` = measured letter-spacing) and the current English. Compare sentence by sentence.
2. Read the views only when needed — a doubtful reading, an `‹…›` the English does not emphasise (or emphasis
   without `‹…›`), a display page (title, headings, tables): run the bundle again without `--no-views` for that page
   and Read its views.
3. Fix with Edit directly in `W/en/sPPP.html` — several Edit calls in one message when you can.
Do not restyle prose that is correct, do not touch anchors unless they are wrong, do not build or render.

## What to look for, in order
1. Sense: dropped or inserted negations, wrong subject/object, misparsed or elliptical constructions, reported
   speech made into assertion, misread words (Fraktur ſ/f, B/V, k/t), wrong tense or mood.
2. Omissions and additions: a clause, a parenthesis, a qualifier ("only", "already", "also"), a doubled word;
   content cut to avoid overflow — restore it.
3. Page joins: the English page starts and ends where the original does — no duplicated or missing words at either
   seam (check the neighbouring English, also across batch boundaries).
4. Emphasis exactly where the print letter-spaces; footnote marks and notes (`note cont`); quotations complete and
   marked per the glossary.
5. Glossary consistency (terms, names, references, spelling); folio and signatures as printed (never "corrected").
If you need a helper script, name it `{{RID}}_*.py` (other reviewers share the folder) and grep-verify its edits.

## Finish
`cd W/.. && scripts/py check.py work FIRST LAST && scripts/py seams.py work FIRST LAST`
Log the fixes to `W/notes/{{RID}}.md` (page: old → new, one line each). Final reply: number of fixes by type
(sense / omission / join / emphasis / terms / other) and anything unresolved.
