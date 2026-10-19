/* app.js */

/* ── Copy-to-clipboard ───────────────────────────────────────────── */
document.addEventListener('click', function (e) {
    var btn = e.target.closest('.copy-btn');
    if (!btn) return;
    var text = btn.dataset.copy;
    if (!text) return;
    navigator.clipboard.writeText(text).then(function () {
        var orig = btn.innerHTML;
        btn.innerHTML = '✓';
        setTimeout(function () { btn.innerHTML = orig; }, 1200);
    });
});

/* ── Ping badge live updates ─────────────────────────────────────── */
(function () {
    function refreshPingBadges() {
        fetch('/api/ping-statuses')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.querySelectorAll('[data-ping-badge]').forEach(function (el) {
                    var id = el.dataset.pingBadge;
                    if (!data[id]) return;
                    el.textContent = data[id].text;
                    el.className = 'status-badge ' + data[id].css;
                });
            })
            .catch(function () {});
    }
    refreshPingBadges();
    setInterval(refreshPingBadges, 30000);
})();

/* ── Three-up QR modal ───────────────────────────────────────────── */
(function () {
    var openBtn = document.getElementById('open-three-up-qr-modal');
    var modal = document.getElementById('three-up-qr-modal');
    var closeBtn = document.getElementById('close-three-up-qr-modal');
    var overlay = modal && modal.querySelector('.three-up-qr-modal-overlay');

    if (!openBtn || !modal) return;

    openBtn.addEventListener('click', function () { modal.hidden = false; });
    closeBtn && closeBtn.addEventListener('click', function () { modal.hidden = true; });
    overlay && overlay.addEventListener('click', function () { modal.hidden = true; });
})();


/* ── Bulk select ─────────────────────────────────────────────────── */
(function () {
    var toggle = document.getElementById('bulk-select-toggle');
    var form = document.getElementById('bulk-action-form');
    var cancel = document.getElementById('bulk-cancel');
    var countEl = document.getElementById('bulk-count');
    var selectAllBtn = document.getElementById('bulk-select-all');
    var card = document.getElementById('assets-overview-card');
    if (!toggle || !form || !card) return;

    var selected = new Set();

    function updateCount() {
        if (countEl) countEl.textContent = selected.size;
    }

    function allCards() {
        return Array.from(card.querySelectorAll('.asset-card:not([hidden])'));
    }

    function syncHiddenInputs() {
        form.querySelectorAll('input[name="asset_ids"]').forEach(function (el) { el.remove(); });
        selected.forEach(function (id) {
            var inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'asset_ids';
            inp.value = id;
            form.appendChild(inp);
        });
    }

    function toggleCard(article) {
        var id = article.dataset.assetId;
        if (!id) return;
        if (selected.has(id)) {
            selected.delete(id);
            article.classList.remove('is-selected');
        } else {
            selected.add(id);
            article.classList.add('is-selected');
        }
        syncHiddenInputs();
        updateCount();
    }

    toggle.addEventListener('click', function () {
        var isActive = card.classList.toggle('bulk-select-mode');
        toggle.textContent = isActive ? 'Done' : 'Select';
        form.hidden = !isActive;
        if (!isActive) {
            selected.clear();
            allCards().forEach(function (a) { a.classList.remove('is-selected'); });
            updateCount();
        }
    });

    if (cancel) {
        cancel.addEventListener('click', function () { toggle.click(); });
    }

    /* Click anywhere on a card to select/deselect it in bulk mode */
    card.addEventListener('click', function (e) {
        if (!card.classList.contains('bulk-select-mode')) return;
        var article = e.target.closest('.asset-card');
        if (!article) return;
        /* Prevent navigating to asset detail or other links */
        e.preventDefault();
        toggleCard(article);
    });

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function () {
            var cards = allCards();
            var allSelected = cards.every(function (a) { return selected.has(a.dataset.assetId); });
            cards.forEach(function (a) {
                var id = a.dataset.assetId;
                if (allSelected) {
                    selected.delete(id);
                    a.classList.remove('is-selected');
                } else {
                    selected.add(id);
                    a.classList.add('is-selected');
                }
            });
            syncHiddenInputs();
            updateCount();
        });
    }
})();
