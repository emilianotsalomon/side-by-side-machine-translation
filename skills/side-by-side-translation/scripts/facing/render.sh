#!/bin/sh
# render.sh IN.html OUT.pdf [fit.txt]  — headless Chrome print; optional fit-report dump (fit.js writes body[data-fit]).
# Chrome is found from $CHROME, then the usual macOS / Linux / Windows-WSL locations, then PATH.
IN=$1; OUT=$2
find_chrome() {
  for c in "$CHROME" \
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "/Applications/Chromium.app/Contents/MacOS/Chromium" \
           "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
           google-chrome google-chrome-stable chromium chromium-browser chrome brave-browser microsoft-edge \
           "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"; do
    [ -n "$c" ] || continue
    if [ -x "$c" ]; then echo "$c"; return; fi
    p=$(command -v "$c" 2>/dev/null) && { echo "$p"; return; }
  done
}
if [ "$1" = "--find" ]; then find_chrome; exit 0; fi      # doctor.py: only report the binary
CH=$(find_chrome)
if [ -z "$CH" ]; then echo "render.sh: Google Chrome / Chromium not found — install Chrome or set CHROME=/path/to/binary" >&2; exit 1; fi
PROF=$(mktemp -d)
"$CH" --headless=new --disable-gpu --no-first-run --user-data-dir="$PROF" --allow-file-access-from-files \
  --no-pdf-header-footer --virtual-time-budget=120000 --run-all-compositor-stages-before-draw \
  --print-to-pdf="$OUT" "file://$IN" 2>/dev/null
if [ -n "$3" ]; then
  "$CH" --headless=new --disable-gpu --no-first-run --user-data-dir="$PROF" --allow-file-access-from-files \
    --virtual-time-budget=120000 --dump-dom "file://$IN" 2>/dev/null \
    | python3 -c "import sys,re,html;s=sys.stdin.read();m=re.search(r'data-fit=\"([^\"]*)\"',s);print(html.unescape(m.group(1)) if m else 'NO-FIT-DATA')" > "$3"
fi
rm -rf "$PROF"
