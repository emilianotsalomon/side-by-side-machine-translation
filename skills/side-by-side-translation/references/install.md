# Installing the side-by-side-translation skill on another machine

The skill is one folder: `SKILL.md`, `references/`, `scripts/` (the Markdown/HTML tools and `scripts/facing/`, the
scanned-book pipeline), `templates/facing/`, `assets/` (PDF template and the Cormorant Garamond fonts), `agents/`
(lean subagent definitions). Nothing in it refers to a particular user's paths. Three things have to exist on the
machine; `scripts/facing/py scripts/facing/doctor.py` checks them and prints the exact install commands.

## 1. Command-line tools (all local — the OCR never leaves the machine)
| tool | why | macOS (Homebrew) | Debian/Ubuntu |
|---|---|---|---|
| poppler (`pdftoppm`, `pdftotext`, `pdfinfo`) | page images, the PDF's own text layer, page counts | `brew install poppler` | `sudo apt install poppler-utils` |
| Tesseract + languages | OCR of pages without a text layer; `frk` = Fraktur, `deu` `lat` `fra` `ita` `spa` `ell` … | `brew install tesseract tesseract-lang` | `sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-script-frak …` |
| Google Chrome or Chromium | typesets the English (headless print to PDF) | install Chrome | `sudo apt install chromium` or Chrome's .deb; `CHROME=/path` if not found |
| Python 3 with numpy, Pillow, pypdf | line detection, page views, PDF merge | `python3 -m pip install --user numpy pillow pypdf` (or `doctor.py --fix`) | same |

`scripts/facing/py` is the launcher every command uses: it tries `$FACING_PYTHON`, a `.venv` next to the book folders
(`_facing-pipeline/.venv`), `python3` on PATH, `/usr/bin/python3`, Homebrew's. To pin one interpreter for a team:
```bash
python3 -m venv ~/Desktop/claude-folder/_facing-pipeline/.venv
~/Desktop/claude-folder/_facing-pipeline/.venv/bin/pip install numpy pillow pypdf
```
The other scripts (`build_pdf.py`, the Markdown lane) need only the standard library plus Chrome.

## 2. The skill itself
- **Claude Desktop / claude.ai** (Settings → Capabilities → Skills → upload): upload the skill folder as a zip whose
  top level is `side-by-side-translation/SKILL.md …`. It then appears under the user's skills on every device signed
  in to that account.
- **Claude Code** (CLI or desktop Code tab): copy the folder to `~/.claude/skills/side-by-side-translation/`, or
  install the plugin that wraps it (`claude plugin install <path-or-repo>`), which also installs the agents below.
- The scanned-book pipeline writes its work under `~/Desktop/claude-folder/_facing-pipeline/<book>/` by default
  (`new_book.py --root DIR` changes it). Keep that folder: it survives sessions; the scratchpad does not.

## 3. Lean agents (optional but cheaper)
`new_book.py` copies `agents/facing-translator.md` and `agents/facing-reviewer.md` to `~/.claude/agents/`; they are
available as subagent types from the next session (`ls ~/.claude/agents/facing-*.md`). Until then the orchestrator
uses general-purpose agents with the same prompts — the briefs are identical.

## Fonts
Clean-text editions use the bundled Cormorant Garamond (embedded in the PDF). The photocopy edition's English column
uses Hoefler Text where it exists (macOS), else Iowan Old Style, Palatino, Georgia, or the system serif; `fit.js`
re-fits the type to the scan's line pitch on every page, so a different face changes texture, not alignment. Greek in
the clean-text edition falls back to Palatino (macOS); on Linux install a Greek-capable serif (e.g. `fonts-gfs-didot`).

## First run on a new machine
```bash
S=<path to the skill>/scripts/facing
$S/py $S/doctor.py --lang deu,frk            # everything "ok"? else follow its fix lines
$S/py $S/new_book.py test "<some scan>.pdf" --layout facing --kind google --lang deu --first 10 --last 20 --prep
cd ~/Desktop/claude-folder/_facing-pipeline/test && scripts/py bundle.py work s012 s013     # OCR lines + views
```
