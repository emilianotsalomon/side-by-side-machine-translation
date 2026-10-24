"""Book-wide consistency replacements on TEXT nodes only (never inside tags/attributes, so anchors survive).
usage: finalfix.py WORK [--dry]      rules: WORK/finalfix.json = [["regex", "replacement"], ...]"""
import sys, re, glob, json, collections
W = sys.argv[1]
DRY = '--dry' in sys.argv
R = json.load(open(f'{W}/finalfix.json'))
cnt = collections.Counter()
for f in sorted(glob.glob(f'{W}/en/s*.html')):
    s = open(f).read()
    parts = re.split(r'(<[^>]+>|<!--.*?-->)', s)
    for i in range(0, len(parts), 2):
        t = parts[i]
        for a, b in R:
            t, n = re.subn(a, b, t)
            if n:
                cnt[(a, f[-9:-5])] += n
        parts[i] = t
    new = ''.join(parts)
    if new != s and not DRY:
        open(f, 'w').write(new)
for (a, p), n in sorted(cnt.items()):
    print(p, n, a[:50])
print(sum(cnt.values()), 'replacements', '(dry run)' if DRY else '')
