(function () {
    var openBtn = document.getElementById('open-image-search-btn');
    var modal = document.getElementById('image-search-modal');
    if (!openBtn || !modal) return;

    var closeBtn = document.getElementById('image-search-close-btn');
    var form = document.getElementById('image-search-form');
    var input = document.getElementById('image-search-input');
    var submitBtn = document.getElementById('image-search-submit');
    var statusEl = document.getElementById('image-search-status');
    var resultsEl = document.getElementById('image-search-results');

    var assetId = modal.dataset.assetId;
    var brand = (modal.dataset.assetBrand || '').trim();
    var model = (modal.dataset.assetModel || '').trim();
    var name = (modal.dataset.assetName || '').trim();

    function setStatus(message, kind) {
        if (!message) {
            statusEl.hidden = true;
            statusEl.textContent = '';
            statusEl.className = 'image-search-status';
            return;
        }
        statusEl.hidden = false;
        statusEl.textContent = message;
        statusEl.className = 'image-search-status image-search-status-' + (kind || 'info');
    }

    function openModal() {
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        var seed = [brand, model].filter(Boolean).join(' ').trim() || name;
        if (seed && !input.value) {
            input.value = seed;
        }
        setTimeout(function () { input.focus(); input.select(); }, 50);
        if (input.value.trim()) {
            doSearch(input.value.trim());
        }
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = '';
    }

    function doSearch(query) {
        submitBtn.disabled = true;
        resultsEl.innerHTML = '';
        setStatus('Searching…', 'info');
        fetch('/api/image-search?q=' + encodeURIComponent(query))
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
            .then(function (res) {
                submitBtn.disabled = false;
                if (!res.ok) {
                    setStatus(res.body.error || 'Search failed.', 'error');
                    return;
                }
                var results = res.body.results || [];
                if (!results.length) {
                    setStatus('No results found. Try a different query.', 'info');
                    return;
                }
                setStatus(results.length + ' result' + (results.length === 1 ? '' : 's') + '. Click an image to attach it.', 'info');
                results.forEach(function (item) {
                    var card = document.createElement('button');
                    card.type = 'button';
                    card.className = 'image-search-result';
                    card.title = item.title || '';
                    var img = document.createElement('img');
                    img.src = item.thumbnail || item.url;
                    img.alt = item.title || '';
                    img.loading = 'lazy';
                    card.appendChild(img);
                    if (item.width && item.height) {
                        var dims = document.createElement('span');
                        dims.className = 'image-search-result-dims';
                        dims.textContent = item.width + ' × ' + item.height;
                        card.appendChild(dims);
                    }
                    card.addEventListener('click', function () { attachImage(item.url, card); });
                    resultsEl.appendChild(card);
                });
            })
            .catch(function (err) {
                submitBtn.disabled = false;
                setStatus('Search failed: ' + err.message, 'error');
            });
    }

    function attachImage(url, card) {
        Array.from(resultsEl.children).forEach(function (c) { c.classList.remove('is-loading'); });
        card.classList.add('is-loading');
        setStatus('Downloading image…', 'info');

        var body = new FormData();
        body.append('asset_id', assetId);
        body.append('url', url);

        fetch('/api/image-search/download', { method: 'POST', body: body })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
            .then(function (res) {
                card.classList.remove('is-loading');
                if (!res.ok) {
                    setStatus(res.body.error || 'Download failed.', 'error');
                    return;
                }
                setStatus('Image attached. Reloading…', 'success');
                setTimeout(function () { window.location.reload(); }, 600);
            })
            .catch(function (err) {
                card.classList.remove('is-loading');
                setStatus('Download failed: ' + err.message, 'error');
            });
    }

    openBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var query = input.value.trim();
        if (!query) return;
        doSearch(query);
    });
})();
