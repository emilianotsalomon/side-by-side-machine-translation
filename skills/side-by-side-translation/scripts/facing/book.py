"""Per-book settings, read from WORK/book.json (written once at setup; every script reads it).
Only "first"/"last" are required; everything else has the defaults below."""
import json, os

DEFAULTS = {
    "layout": "facing",                    # "facing" = photocopy edition (scan left, English right, like the Hegel
                                           # Encyclopaedia 1817); "retype" = clean-text edition (both columns typeset,
                                           # pagination in the margins, like the Exner) — set by new_book.py
    "first": 1, "last": 9999,              # scan page range of the edition (pages in DROP are skipped)
    "geometry": {"sheet": [960, 760],      # landscape sheet, pt
                 "sc": 0.48,               # scan px -> pt
                 "top": 20.0,              # scan top offset on the sheet, pt
                 "half": 480.0,            # half-sheet width, pt (the scan sits in the left half)
                 "tw": 345,                # English text width, pt
                 "scan_h": 1500},          # scan PNG height, px
    "fit": {"grow": 1.25, "max": 16.5, "drift": 14, "fs_min": 10.5, "fs_max": 14.5},
    "folio": {"format": "— {n} —",         # printed folio; ranges map scan -> printed page
              "ranges": [{"from": 1, "to": 9999, "offset": 0}],
              "none": []},                 # scans with no printed folio (openings, titles)
    "marks": [],                           # printer's signatures, e.g. {"class": "sig", "start": 3, "every": 16, "format": "{k}*"}
    "ocr": {"pdf": "src/orig.pdf", "pdf_offset": 0, "align": "page", "tesseract": "deu"},
    "outline": [],                         # [[scan, "Label", level], ...] PDF bookmarks
    "meta": {"title": "", "author": ""},
    "out": "",                             # deliverable path
}


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def load(work):
    cfg = json.loads(json.dumps(DEFAULTS))
    p = os.path.join(work, 'book.json')
    if os.path.exists(p):
        _merge(cfg, json.load(open(p)))
    cfg['out'] = os.path.expanduser(cfg.get('out') or '')
    dp = os.path.join(work, 'DROP')
    cfg['drop'] = set(open(dp).read().split()) if os.path.exists(dp) else set()
    return cfg


def pages(cfg, a=None, b=None):
    """non-dropped scan numbers in [a, b] as 'sPPP' strings"""
    a = cfg['first'] if a is None else a
    b = cfg['last'] if b is None else b
    return [f's{p:03d}' for p in range(a, b + 1) if f's{p:03d}' not in cfg['drop']]


def roman(n):
    out = ''
    for v, s in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
                 (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out += s; n -= v
    return out


def printed(cfg, scan):
    """printed page label for a scan number, or None"""
    for r in cfg['folio']['ranges']:
        if r['from'] <= scan <= r['to']:
            n = scan + r.get('offset', 0)
            return roman(n) if r.get('roman') else str(n)
    return None


def expected_folio(cfg, scan):
    if scan in cfg['folio']['none']:
        return None
    n = printed(cfg, scan)
    return None if n is None else cfg['folio']['format'].format(n=n)


def expected_marks(cfg, scan):
    """[(class, text)] printer's signatures expected at the foot of this page"""
    out = []
    n = printed(cfg, scan)
    if n is None or not n.isdigit():
        return out
    n = int(n)
    for m in cfg['marks']:
        st, ev = m['start'], m['every']
        if n >= st and (n - st) % ev == 0 and n >= m.get('min', 0):
            k = (n - st) // ev + m.get('k0', 1)
            out.append((m['class'], m['format'].format(k=k, n=n)))
    return out
