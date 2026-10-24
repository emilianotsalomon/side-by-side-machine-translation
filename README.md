# side-by-side-translation (Claude Code plugin)

Turns a scanned PDF of a printed book into a bilingual facing edition, in one of two layouts chosen when the PDF comes in:

- **Photocopy edition** — the original scanned page on the left, newly translated English typeset beside it, aligned line by line, folios and footnotes as printed (like the *Hegel, Encyclopaedia 1817* edition).
- **Clean-text edition** — both columns freshly typeset, original left / English right, the original pagination marked in the margins with a red bar at each page break, footnotes at the foot (like the *Exner, Psychologie der Hegelschen Schule* edition).

It also builds parallel-text HTML readers and print PDFs from two text/Markdown/EPUB files (original + translation).

**All scan processing is local.** OCR uses the PDF's own text layer (poppler) or Tesseract on your machine; page images, typesetting (headless Chrome) and the PDF merge are local too. Only the OCR lines and page views that Claude reads in order to translate leave the machine.

## Install

1. Install the plugin in Claude Code (from the unzipped folder):
   ```bash
   claude plugin install /path/to/side-by-side-translation-plugin
   ```
   or add this folder as a local marketplace / git repository and install from there. The skill and the two lean agents (`facing-translator`, `facing-reviewer`) are installed together.
2. Install the local tools (macOS, Homebrew):
   ```bash
   brew install poppler tesseract tesseract-lang
   python3 -m pip install --user numpy pillow pypdf
   ```
   plus Google Chrome. Linux equivalents and details: `skills/side-by-side-translation/references/install.md`.
3. Check the machine:
   ```bash
   skills/side-by-side-translation/scripts/facing/py doctor.py --lang deu,frk
   ```

## Use

In a Claude Code session, give it the PDF and ask for a side-by-side translation ("scope and plan out a side by side translation of this into English, keep original pagination"). Claude asks photocopy or clean-text, then sets the book up with `new_book.py` under `~/Desktop/claude-folder/_facing-pipeline/<book>/` (persistent; change with `--root`), translates with subagents, reviews, and builds the PDF with `make.py`.

Where things are: the skill's `SKILL.md` (entry point), `references/facing-edition.md` (the scanned-book pipeline), `references/install.md` (per-machine setup), `scripts/facing/` (pipeline), `templates/facing/` (agent briefs and config), `assets/` (PDF template and fonts), `agents/` (lean subagents).

## Checks
`tests/smoke.sh` runs both pipelines end to end on tiny fixtures (a few seconds; needs what `doctor.py` checks for). GitHub Actions (`.github/workflows/ci.yml`) runs it and the `ruff` linter on every push and pull request.
