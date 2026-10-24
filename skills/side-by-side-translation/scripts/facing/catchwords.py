"""Catchwords (<p class="cw">) against the next page's first English word.  Translators write any word there;
this reports every catchword that does not begin like the next page, and --apply sets those to that word (with <em>
if it is emphasised there).  Hand-set forms that already match ("“a)", "I. Over-") are left alone.
usage: catchwords.py WORK [--apply]"""
import sys, re, os, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book
W = sys.argv[1]
cfg = book.load(W)
pl = book.pages(cfg)
norm = lambda t: re.sub(r'\W', '', html.unescape(re.sub('<[^>]+>', '', t))).lower()
n = 0
for x, y in zip(pl, pl[1:]):
    fx, fy = f'{W}/en/{x}.html', f'{W}/en/{y}.html'
    if not (os.path.exists(fx) and os.path.exists(fy)):
        continue
    s = open(fx).read()
    cw = re.search(r'<p class="cw"[^>]*>(.*?)</p>', s, re.S)
    if not cw:
        continue
    t = re.sub(r'<p class="(rh|sig|sigf|cw)[^"]*".*?</p>|<hr[^>]*>|<!--.*?-->', ' ', open(fy).read(), flags=re.S)
    m = re.search(r'>\s*((?:<em>)?)([^<\s]+)', t)
    if not m:
        continue
    word = re.sub(r'[,;:.]+$', '', m.group(2))
    have, want = norm(cw.group(1)), norm(word)
    if have and want and (want.startswith(have) or have.startswith(want)):
        continue
    n += 1
    new = f'<em>{word}</em>' if m.group(1) else word
    print(f'{x}: catchword {html.unescape(re.sub("<[^>]+>", "", cw.group(1)))!r} -> {word!r}')
    if '--apply' in sys.argv:
        open(fx, 'w').write(s[:cw.start(1)] + new + s[cw.end(1):])
print(n, 'catchwords', 'set' if '--apply' in sys.argv else 'differ (run with --apply to set them)')
