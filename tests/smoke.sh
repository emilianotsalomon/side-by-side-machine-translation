#!/bin/sh
# smoke.sh — run both pipelines end to end on tiny fixtures (a few seconds).  Needs what doctor.py checks for.
#   tests/smoke.sh            (from the repository root; FACING_PYTHON / CHROME are honoured as usual)
# 1. Markdown lane: md_edition.py on a three-section es/en pair → PDF + HTML.
# 2. Photocopy edition: new_book.py on a two-page scan, the fixture English pages, make.py → PDF (exit 0);
#    then one page overfilled → make.py must exit 3.
set -eu
R=$(cd "$(dirname "$0")/.." && pwd)
S=$R/skills/side-by-side-translation/scripts
FX=$R/tests/fixtures
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
PY=${FACING_PYTHON:-python3}

echo "== markdown lane"
"$PY" "$S/md_edition.py" "$FX/orig.md" "$FX/trans.md" --author Test --work "<i>Smoke test</i>" \
  --lang es en -o "$T/md.pdf" --html "$T/md.html"
test -s "$T/md.pdf" && test -s "$T/md.html"

echo "== photocopy edition"
"$S/facing/py" new_book.py smoke "$FX/scan.pdf" --layout facing --kind plain --lang deu --first 1 --last 2 \
  --root "$T/books" --out "$T/facing.pdf" --prep --no-agents
B=$T/books/smoke
cp "$FX"/en/s00*.html "$B/work/en/"
(cd "$B" && scripts/py make.py work)
test -s "$T/facing.pdf"

echo "== overflow is an error"
"$PY" -c "import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.replace('</p>', ' ' + 'More text. ' * 400 + '</p>'))" \
  "$B/work/en/s002.html"
rc=0; (cd "$B" && scripts/py make.py work >/dev/null) || rc=$?
if [ "$rc" != 3 ]; then echo "expected make.py to exit 3 on overflow, got $rc" >&2; exit 1; fi
echo "smoke: ok"
