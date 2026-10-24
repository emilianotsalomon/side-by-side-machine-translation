/* Shared annotations for the reader: highlights (three faded colours), underlines, strikeouts and comments,
   stored in the repository as annotations/<text>.json and written through the GitHub API with a personal token
   each annotator pastes once (kept in this browser only). Reading needs no token.  Toggles: annotations, comments. */
(function () {
  const CFG = window.ANNOT || {};
  const REPO = CFG.repo, BRANCH = CFG.branch || 'main', REL = CFG.rel;           // e.g. "owner/name", "exner-…"
  if (!REPO || !REL) return;
  const PATH = `annotations/${REL}.json`;
  const API = `https://api.github.com/repos/${REPO}/contents/${PATH}`;
  const main = document.querySelector('main'); if (!main) return;
  const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
                  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  let items = [], sha = null, user = store.get('annot-user') || '';
  const token = () => store.get('annot-token') || '';
  const showAn = () => store.get('annot-show') !== 'off', showCm = () => store.get('annot-comments') !== 'off';

  // ---------- UI scaffolding ----------
  const top = document.querySelector('.top .in');
  const ctl = document.createElement('div'); ctl.className = 'an-ctl';
  ctl.innerHTML = `<label><input type="checkbox" id="an-show"> annotations</label><label><input type="checkbox" id="an-cm"> comments</label>
    <button id="an-who" class="an-btn" title="GitHub token for annotating"></button>`;
  top.appendChild(ctl);
  const cbA = ctl.querySelector('#an-show'), cbC = ctl.querySelector('#an-cm'), who = ctl.querySelector('#an-who');
  cbA.checked = showAn(); cbC.checked = showCm();
  cbA.onchange = () => { store.set('annot-show', cbA.checked ? 'on' : 'off'); render(); };
  cbC.onchange = () => { store.set('annot-comments', cbC.checked ? 'on' : 'off'); render(); };
  const page = document.querySelector('.page');
  const gutter = document.createElement('aside'); gutter.className = 'an-gutter'; page.appendChild(gutter);
  const bar = document.createElement('div'); bar.className = 'an-bar hidden';
  bar.innerHTML = `<button data-t="hl" data-c="straw" title="highlight"><i class="sw straw"></i></button><button data-t="hl" data-c="sage" title="highlight"><i class="sw sage"></i></button>
    <button data-t="hl" data-c="rose" title="highlight"><i class="sw rose"></i></button><button data-t="ul" title="underline"><u>U</u></button>
    <button data-t="st" title="strike out"><s>S</s></button><button data-t="cm" title="comment">✎</button>`;
  document.body.appendChild(bar);
  const dlg = document.createElement('div'); dlg.className = 'an-dlg hidden';
  dlg.innerHTML = `<div class="an-box"><h3>Annotate as a member of the group</h3>
    <p>Annotations are saved in the repository <b>${REPO}</b> so that everyone sees them. To write, the reader needs a GitHub
    <b>fine-grained personal access token</b> for that repository with <b>Contents: read and write</b>. It is stored in this browser only.
    Create one at <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">github.com → Settings → Developer settings → Fine-grained tokens</a>
    (Repository access: only <i>${REPO.split('/')[1]}</i>; Permissions: Contents → Read and write).</p>
    <label>Your name or initials, as shown next to your notes<input id="an-name" placeholder="E. S."></label>
    <label>Token<input id="an-tok" type="password" placeholder="github_pat_…"></label>
    <div class="an-row"><button id="an-save" class="an-btn">Save</button><button id="an-forget" class="an-btn">Forget token</button><button id="an-close" class="an-btn">Close</button></div></div>`;
  document.body.appendChild(dlg);
  const setWho = () => { who.textContent = token() ? (user || 'annotating') : 'sign in to annotate'; };
  setWho();
  who.onclick = () => { dlg.querySelector('#an-name').value = user; dlg.querySelector('#an-tok').value = token(); dlg.classList.remove('hidden'); };
  dlg.querySelector('#an-close').onclick = () => dlg.classList.add('hidden');
  dlg.querySelector('#an-forget').onclick = () => { store.set('annot-token', ''); setWho(); dlg.classList.add('hidden'); };
  dlg.querySelector('#an-save').onclick = () => { user = dlg.querySelector('#an-name').value.trim(); store.set('annot-user', user);
    store.set('annot-token', dlg.querySelector('#an-tok').value.trim()); setWho(); dlg.classList.add('hidden'); };

  // ---------- storage ----------
  async function load() {
    try {
      const r = await fetch(API + `?ref=${BRANCH}&t=${Date.now()}`, { headers: token() ? { Authorization: 'Bearer ' + token() } : {} });
      if (r.status === 404) { items = []; sha = null; throw new Error('none yet'); }   // fall back to the site's own copy
      if (!r.ok) throw new Error(r.status);
      const j = await r.json(); sha = j.sha;
      items = JSON.parse(decodeURIComponent(escape(atob(j.content.replace(/\n/g, ''))))).items || [];
    } catch (e) {
      try { const r2 = await fetch(`${CFG.base || ''}${PATH}?t=${Date.now()}`); if (r2.ok) items = (await r2.json()).items || []; } catch (e2) {}
    }
  }
  async function save(msg) {
    if (!token()) { who.click(); return false; }
    const body = JSON.stringify({ items }, null, 1);
    const payload = { message: msg, content: btoa(unescape(encodeURIComponent(body))), branch: BRANCH };
    if (sha) payload.sha = sha;
    let r = await fetch(API, { method: 'PUT', headers: { Authorization: 'Bearer ' + token(), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (r.status === 409 || r.status === 422) {               // someone saved meanwhile: merge and retry once
      const mine = items.slice(); await load();
      const ids = new Set(items.map(x => x.id)); mine.forEach(x => { if (!ids.has(x.id) && !x._del) items.push(x); });
      items = items.filter(x => !mine.find(m => m.id === x.id && m._del));
      payload.content = btoa(unescape(encodeURIComponent(JSON.stringify({ items }, null, 1)))); payload.sha = sha;
      r = await fetch(API, { method: 'PUT', headers: { Authorization: 'Bearer ' + token(), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
    if (!r.ok) { alert('Could not save the annotation (GitHub answered ' + r.status + '). Check the token and its permissions.'); return false; }
    sha = (await r.json()).content.sha; return true;
  }

  // ---------- anchoring: quote + prefix/suffix inside one page box ----------
  function textNodes(root) { const out = []; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) out.push(n); return out; }
  function offsets(root) { const nodes = textNodes(root); let s = '', map = []; nodes.forEach(n => { map.push([s.length, n]); s += n.data; }); return { s, map }; }
  function locate(root, a) {
    const { s, map } = offsets(root); const q = a.quote; if (!q) return null;
    let i = -1, best = -1, bestScore = -1;
    while ((i = s.indexOf(q, i + 1)) !== -1) {
      let sc = 0; if (a.prefix && s.slice(Math.max(0, i - a.prefix.length), i) === a.prefix) sc += 2;
      if (a.suffix && s.slice(i + q.length, i + q.length + a.suffix.length) === a.suffix) sc += 2;
      if (sc > bestScore) { bestScore = sc; best = i; } if (sc === 4) break;
    }
    if (best < 0) return null;
    const range = document.createRange();
    const pos = k => { let last = map[0]; for (const m of map) { if (m[0] <= k) last = m; else break; } return [last[1], k - last[0]]; };
    const [n1, o1] = pos(best), [n2, o2] = pos(best + q.length);
    range.setStart(n1, o1); range.setEnd(n2, o2); return range;
  }
  function wrap(range, cls, id) {               // split the range into per-text-node ranges and wrap each
    const nodes = textNodes(range.commonAncestorContainer.nodeType === 3 ? range.commonAncestorContainer.parentNode : range.commonAncestorContainer)
      .filter(n => range.intersectsNode(n));
    const marks = [];
    nodes.forEach(n => {
      const r = document.createRange(); r.selectNodeContents(n);
      if (n === range.startContainer) r.setStart(n, range.startOffset);
      if (n === range.endContainer) r.setEnd(n, range.endOffset);
      if (r.collapsed) return;
      const m = document.createElement('mark'); m.className = 'an ' + cls; m.dataset.id = id; r.surroundContents(m); marks.push(m);
    });
    return marks;
  }
  function unwrapAll() { main.querySelectorAll('mark.an').forEach(m => { const p = m.parentNode; while (m.firstChild) p.insertBefore(m.firstChild, m); p.removeChild(m); p.normalize(); }); gutter.innerHTML = ''; }

  // ---------- rendering ----------
  function render() {
    unwrapAll();
    if (!showAn()) { document.body.classList.remove('an-with-comments'); return; }
    const cms = [];
    items.forEach(a => {
      const card = document.getElementById(a.card) || main; const range = locate(card, a) || (card !== main && locate(main, a)); if (!range) return;
      const cls = a.type === 'hl' ? 'hl ' + (a.color || 'straw') : a.type;
      const marks = wrap(range, cls, a.id);
      if (a.type === 'cm' && marks.length) cms.push([a, marks[0]]);
    });
    document.body.classList.toggle('an-with-comments', showCm() && cms.length > 0);
    if (!showCm()) return;
    const mainTop = main.getBoundingClientRect().top + window.scrollY; let bottom = 0;
    cms.sort((x, y) => x[1].getBoundingClientRect().top - y[1].getBoundingClientRect().top).forEach(([a, m]) => {
      const el = document.createElement('div'); el.className = 'an-cm'; el.dataset.id = a.id;
      el.innerHTML = `<div class="an-meta"><b>${esc(a.user || '—')}</b> · ${esc((a.time || '').slice(0, 10))}${a.user === user && token() ? ' <button class="an-x" title="delete">×</button>' : ''}</div><div class="an-q">“${esc(a.quote.slice(0, 80))}${a.quote.length > 80 ? '…' : ''}”</div><div class="an-t">${esc(a.text || '')}</div>`;
      let y = m.getBoundingClientRect().top + window.scrollY - mainTop; if (y < bottom + 8) y = bottom + 8;
      el.style.top = y + 'px'; gutter.appendChild(el); bottom = y + el.offsetHeight;
      el.onmouseenter = () => main.querySelectorAll(`mark[data-id="${a.id}"]`).forEach(x => x.classList.add('on'));
      el.onmouseleave = () => main.querySelectorAll(`mark[data-id="${a.id}"]`).forEach(x => x.classList.remove('on'));
      el.onclick = e => { if (e.target.classList.contains('an-x')) return; m.scrollIntoView({ block: 'center', behavior: 'smooth' }); };
      const x = el.querySelector('.an-x'); if (x) x.onclick = async () => { if (!confirm('Delete this comment?')) return; items = items.filter(i => i.id !== a.id); render(); await save(`Delete comment by ${user}`); };
    });
  }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  main.addEventListener('click', async e => {               // click a mark: offer to remove it (marks have no card in the gutter)
    const m = e.target.closest('mark.an'); if (!m || m.classList.contains('cm')) return;
    const a = items.find(i => i.id === m.dataset.id); if (!a || !token()) return;
    if (confirm(`Remove this ${a.type === 'hl' ? 'highlight' : a.type === 'ul' ? 'underline' : 'strikeout'} (by ${a.user || '—'})?`)) { items = items.filter(i => i.id !== a.id); render(); await save(`Remove ${a.type} by ${user}`); }
  });

  // ---------- selection toolbar ----------
  function selectionInfo() {
    const sel = window.getSelection(); if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const r = sel.getRangeAt(0); const card = r.commonAncestorContainer.nodeType === 1 ? r.commonAncestorContainer.closest('.card') : r.commonAncestorContainer.parentNode.closest('.card');
    if (!card || !main.contains(card)) return null;
    const quote = r.toString(); if (!quote.trim() || quote.length > 2000) return null;
    const { s, map } = offsets(card);
    const start = (() => { for (const [off, n] of map) if (n === r.startContainer) return off + r.startOffset; return -1; })();
    if (start < 0) return null;
    return { card: card.id, quote, prefix: s.slice(Math.max(0, start - 32), start), suffix: s.slice(start + quote.length, start + quote.length + 32), rect: r.getBoundingClientRect() };
  }
  let pending = null;
  document.addEventListener('mouseup', () => setTimeout(() => {
    const info = selectionInfo(); if (!info || !showAn()) { bar.classList.add('hidden'); return; }
    pending = info; bar.style.left = Math.max(8, info.rect.left + window.scrollX + info.rect.width / 2 - bar.offsetWidth / 2) + 'px';
    bar.style.top = (info.rect.top + window.scrollY - 44) + 'px'; bar.classList.remove('hidden');
  }, 10));
  document.addEventListener('mousedown', e => { if (!bar.contains(e.target)) bar.classList.add('hidden'); });
  bar.querySelectorAll('button').forEach(b => b.onclick = async () => {
    if (!pending) return; const t = b.dataset.t; if (!token()) { who.click(); return; }
    const a = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), user, time: new Date().toISOString(), type: t,
                card: pending.card, quote: pending.quote, prefix: pending.prefix, suffix: pending.suffix };
    if (t === 'hl') a.color = b.dataset.c;
    if (t === 'cm') { const text = prompt('Comment:'); if (!text) return; a.text = text; }
    bar.classList.add('hidden'); window.getSelection().removeAllRanges();
    items.push(a); render(); await save(`${t === 'cm' ? 'Comment' : 'Mark'} by ${user || 'anonymous'} on ${REL}`);
  });
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(render, 150); });
  load().then(render);
})();
