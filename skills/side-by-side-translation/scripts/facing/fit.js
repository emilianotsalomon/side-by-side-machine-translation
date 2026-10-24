// Align each English block to the height of its German line; place margin notes; shrink type on overflow,
// grow it (up to data-grow pt, max data-max) while the text still ends above the German last line (data-end).
// Every anchored element carries data-y (pt from sheet top).  Diagnostics go into body[data-fit].
(function () {
  const PX = 4 / 3;
  const report = [];
  function fit(sheet) {
    const body = sheet.querySelector('.body');
    if (!body) return;
    const blocks = Array.from(body.children).filter(e => !e.classList.contains('mn'));
    const notes = Array.from(sheet.querySelectorAll('.mn'));
    let fs = parseFloat(body.dataset.fs || '12');
    const lh = parseFloat(body.dataset.lh || '1.24');
    const H = body.clientHeight;
    const DRIFT = parseFloat(body.dataset.drift || '14'), GROW = parseFloat(body.dataset.grow || '1.25'),
          MAX = parseFloat(body.dataset.max || '16.5');
    let drift = 0, over = 0;
    for (let it = 0; it < 30; it++) {
      body.style.fontSize = fs + 'pt';
      body.style.lineHeight = (fs * lh) + 'pt';
      blocks.forEach(b => b.style.removeProperty('margin-top'));
      drift = 0;
      for (const b of blocks) {
        if (b.dataset.y === undefined) continue;
        const target = parseFloat(b.dataset.y) * PX;
        const cur = b.offsetTop;
        if (target > cur + 0.5) b.style.setProperty('margin-top', (target - cur) + 'px', 'important');
        else drift = Math.max(drift, (cur - target) / PX);
      }
      const last = blocks[blocks.length - 1];
      over = last ? (last.offsetTop + last.offsetHeight - H) / PX : 0;
      const base = parseFloat(body.dataset.fs || '12');
      if (fs <= 8) break;
      if (over <= 0.5 && (drift <= DRIFT || fs <= Math.min(11.25, base - 1))) break;
      fs -= 0.25;
    }
    // grow type while the text still ends above the German last line
    const end = body.dataset.end ? parseFloat(body.dataset.end) * PX : 0;
    function layout(f) {
      body.style.fontSize = f + 'pt';
      body.style.lineHeight = (f * lh) + 'pt';
      blocks.forEach(b => b.style.removeProperty('margin-top'));
      let d = 0;
      for (const b of blocks) {
        if (b.dataset.y === undefined) continue;
        const target = parseFloat(b.dataset.y) * PX;
        const cur = b.offsetTop;
        if (target > cur + 0.5) b.style.setProperty('margin-top', (target - cur) + 'px', 'important');
        else d = Math.max(d, (cur - target) / PX);
      }
      // keep >= 3pt clear above every rule (section rules, footnote rules) when growing type
      for (const b of blocks) {
        const pr = b.previousElementSibling;
        if (b.tagName === 'HR' && pr && b.offsetTop - (pr.offsetTop + pr.offsetHeight) < 3 * PX) d = Math.max(d, 99);
      }
      const l = blocks[blocks.length - 1];
      return [d, l ? l.offsetTop + l.offsetHeight : 0];
    }
    if (end && over <= 0.5 && fs >= parseFloat(body.dataset.fs || '12')) {
      const base0 = fs;
      const [, bot0] = layout(fs);
      const lim = Math.max(end, bot0) + 3 * PX;
      let best = fs;
      for (let f = fs + 0.25; f <= Math.min(MAX, base0 + GROW); f += 0.25) {
        const [d, bot] = layout(f);
        if (d <= 9 && bot <= lim && bot <= H) best = f; else break;
      }
      const [d1, b1] = layout(best);
      drift = d1; over = (b1 - H) / PX;
      fs = best;
    }
    // margin notes: at their line, pushed down if they collide
    let bottom = -1e9;
    for (const n of notes) {
      let t = parseFloat(n.dataset.y) * PX;
      if (t < bottom + 2) t = bottom + 2;
      n.style.top = t + 'px';
      bottom = t + n.offsetHeight;
    }
    const nOver = notes.length ? (bottom - H) / PX : 0;
    const p = sheet.dataset.p;
    if (fs != parseFloat(body.dataset.fs || '12') || drift > 12 || over > 0.5 || nOver > 0.5)
      report.push(`${p} fs=${fs} drift=${drift.toFixed(0)} over=${over.toFixed(0)} nover=${nOver.toFixed(0)}`);
    if (over > 0.5 || nOver > 0.5) sheet.classList.add('bad');
  }
  function run() {
    document.querySelectorAll('.sheet').forEach(fit);
    document.body.dataset.fit = report.join('\n');
    document.body.dataset.done = '1';
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(run); else run();
})();
