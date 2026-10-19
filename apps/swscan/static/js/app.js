// Mount path when served under a proxy prefix (e.g. /scan in SWSuite);
// empty string when running standalone.
const BASE = window.BASE_PATH || '';

// SWScan v1.0 client
(function () {
  // ---- job progress polling ----
  const panel = document.getElementById('progress-panel');
  if (panel && !['complete', 'failed'].includes(panel.dataset.status)) {
    const jobId = panel.dataset.job;
    const poll = async () => {
      try {
        const r = await fetch(`${BASE}/api/jobs/${jobId}`);
        const d = await r.json();
        document.getElementById('progress-fill').style.width = d.progress + '%';
        const badge = document.getElementById('job-badge');
        badge.textContent = d.status;
        badge.className = 'badge ' + d.status;
        document.getElementById('job-message').textContent =
          d.message || `Frames analyzed: ${d.frames_analyzed} / ${d.frames_total}`;
        if (d.status === 'complete' || d.status === 'failed') {
          setTimeout(() => location.reload(), 800);
          return;
        }
      } catch (e) { /* transient, keep polling */ }
      setTimeout(poll, 2500);
    };
    poll();
  }

  // ---- find images (SearXNG) ----
  const findBtn = document.getElementById('find-images');
  if (findBtn) {
    findBtn.addEventListener('click', async () => {
      const results = document.getElementById('image-results');
      results.innerHTML = '<p class="empty">Searching…</p>';
      try {
        const r = await fetch(`${BASE}/api/items/${findBtn.dataset.item}/find-images`);
        const d = await r.json();
        if (d.error) { results.innerHTML = `<p class="empty">${d.error}</p>`; return; }
        if (!d.results.length) { results.innerHTML = '<p class="empty">No results.</p>'; return; }
        results.innerHTML = '';
        d.results.forEach(img => {
          const a = document.createElement('a');
          a.className = 'thumb';
          a.href = '#';
          a.innerHTML = `<img src="${img.url}" loading="lazy" alt=""><span>use this</span>`;
          a.addEventListener('click', e => {
            e.preventDefault();
            document.getElementById('image-url').value = img.url;
            a.querySelector('span').textContent = 'selected ✓ (save to keep)';
          });
          results.appendChild(a);
        });
      } catch (e) {
        results.innerHTML = '<p class="empty">Search failed.</p>';
      }
    });
  }
})();

// ---- review slideshow ----
(function () {
  const root = document.getElementById('review');
  if (!root) return;
  const ids = JSON.parse(root.dataset.items);
  let i = 0;

  const el = id => document.getElementById(id);
  const imageBox = el('rv-image'), nameEl = el('rv-name'), nameInput = el('rv-name-input');

  async function load() {
    el('rv-pos').textContent = i + 1;
    imageBox.innerHTML = '<div class="spinner">loading…</div>';
    el('rv-status').textContent = '';
    try {
      const r = await fetch(`${BASE}/api/items/${ids[i]}`);
      const d = await r.json();
      nameEl.textContent = d.name;
      nameInput.value = d.name;
      el('rv-cat').textContent = d.category;
      el('rv-qty').textContent = d.quantity;
      el('rv-cond').textContent = d.condition || '';
      el('rv-zone').textContent = d.zone ? 'zone ' + d.zone : '';
      imageBox.innerHTML = d.image
        ? `<img src="${d.image}" alt="${d.name}">`
        : '<div class="spinner">no image</div>';
      if (d.verified !== 'unverified') {
        el('rv-status').innerHTML = d.verified === 'confirmed'
          ? '<span class="badge complete">✓ confirmed</span>'
          : '<span class="badge failed">✗ rejected</span>';
      }
    } catch (e) { imageBox.innerHTML = '<div class="spinner">load failed</div>'; }
  }

  async function verdict(action) {
    try {
      await fetch(`${BASE}/api/items/${ids[i]}/verdict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, name: nameInput.value }),
      });
    } catch (e) { /* ignore, still advance */ }
    next();
  }

  function next() { if (i < ids.length - 1) { i++; load(); } else { finish(); } }
  function prev() { if (i > 0) { i--; load(); } }
  function finish() {
    root.innerHTML = '<div class="panel"><p class="empty">Review complete. '
      + '<a href="' + BASE + '/catalog">Back to catalog</a></p></div>';
  }

  el('rv-confirm').addEventListener('click', () => verdict('confirm'));
  el('rv-reject').addEventListener('click', () => verdict('reject'));
  el('rv-skip').addEventListener('click', next);
  el('rv-prev').addEventListener('click', prev);

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') {
      if (e.key === 'Enter') { e.preventDefault(); verdict('confirm'); }
      return;
    }
    if (e.key === 'c' || e.key === 'C') verdict('confirm');
    else if (e.key === 'r' || e.key === 'R') verdict('reject');
    else if (e.key === 'ArrowRight') next();
    else if (e.key === 'ArrowLeft') prev();
  });

  load();
})();
