"""True token cost of a job (main agent + every subagent), from the Claude Code transcripts.
usage: usage.py [SESSION_ID | latest] [--pages N] [--project DIR]   (run from the book folder or the project folder)
The "tokens" an Agent result reports is its final context size, NOT what it consumed: a 20-page translator that
"used 150k" typically re-read 30-90M cached tokens.  This sums every API call (deduplicated by message id) and
prints per agent: calls, cache writes, cache reads, output, peak context, images — plus input-equivalent tokens
(read x0.1, write x1.25, output x5; multiply by the model's input price for money)."""
import sys, os, glob, json, re, collections

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = dict(zip(sys.argv[1::1], sys.argv[2::1]))
def project_dir():
    """Claude Code keeps transcripts in ~/.claude/projects/<cwd with / and . replaced by ->; the book folders live
    under the session's working directory, so walk up from here until such a folder exists"""
    d = os.getcwd()
    while True:
        cand = os.path.expanduser('~/.claude/projects/' + re.sub(r'[/.]', '-', d))
        if os.path.isdir(cand):
            return cand
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    cands = glob.glob(os.path.expanduser('~/.claude/projects/*/'))
    return max(cands, key=os.path.getmtime).rstrip('/') if cands else os.path.expanduser('~/.claude/projects')


proj = opt.get('--project') or project_dir()
sid = args[0] if args and args[0] != 'latest' else \
    os.path.basename(max(glob.glob(f'{proj}/*.jsonl'), key=os.path.getmtime))[:-6]
NP = int(opt['--pages']) if '--pages' in opt else 0


def scan(path):
    seen, imgs, first, model = {}, 0, '', None
    for raw in open(path, 'rb'):
        if len(raw) > 2_000_000:
            imgs += raw.count(b'"type":"image"'); continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        m = d.get('message') or {}
        c = m.get('content')
        if d.get('type') == 'user' and not first:
            first = c if isinstance(c, str) else next((b.get('text', '') for b in c or [] if b.get('type') == 'text'), '')
        if isinstance(c, list):
            imgs += sum(1 for b in c if b.get('type') == 'tool_result' and isinstance(b.get('content'), list)
                        for x in b['content'] if x.get('type') == 'image')
        if d.get('type') == 'assistant' and m.get('usage') and m.get('id'):
            seen[m['id']] = m['usage']
            if m.get('model', '').startswith('claude'):
                model = m['model']
    t = collections.Counter()
    peak = 0
    for u in seen.values():
        cw, cr = u.get('cache_creation_input_tokens') or 0, u.get('cache_read_input_tokens') or 0
        t['cw'] += cw; t['cr'] += cr; t['in'] += u.get('input_tokens') or 0; t['out'] += u.get('output_tokens') or 0
        peak = max(peak, cw + cr)
    return dict(model=model or '?', calls=len(seen), imgs=imgs, peak=peak, first=first, **t)


def ieq(r):
    return r['in'] + 0.1 * r['cr'] + 1.25 * r['cw'] + 5 * r['out']


def k(n):
    return f'{n / 1e6:.1f}M' if n >= 1e6 else f'{n / 1e3:.0f}k'


rows = [('main', scan(f'{proj}/{sid}.jsonl'))]
for f in sorted(glob.glob(f'{proj}/{sid}/subagents/*.jsonl')):
    meta = f[:-6] + '.meta.json'
    desc = json.load(open(meta)).get('description', '') if os.path.exists(meta) else ''
    rows.append((desc or os.path.basename(f)[:14], scan(f)))
print(f'session {sid}')
print(f'{"agent":34} {"model":17} {"calls":>5} {"c.write":>8} {"c.read":>8} {"out":>7} {"peak":>6} {"img":>4} {"in-eq":>7}')
tot = collections.defaultdict(collections.Counter)
for name, r in rows:
    print(f'{name[:34]:34} {r["model"][:17]:17} {r["calls"]:5} {k(r["cw"]):>8} {k(r["cr"]):>8} {k(r["out"]):>7} '
          f'{k(r["peak"]):>6} {r["imgs"]:4} {k(ieq(r)):>7}')
    for key in ('in', 'cw', 'cr', 'out', 'calls'):
        tot[r['model']][key] += r[key]
for m, t in tot.items():
    line = f'TOTAL {m}: calls {t["calls"]}, cache write {k(t["cw"])}, cache read {k(t["cr"])}, output {k(t["out"])}, input-equivalent {k(ieq(t))}'
    print(line + (f'  = {k(ieq(t) / NP)} per page' if NP else ''))
print('Peak context above ~180k means auto-trimming of old tool results and repeated full cache rewrites: smaller batches.')
