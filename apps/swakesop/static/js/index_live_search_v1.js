(function () {
    var input = document.querySelector('.search-input-wrap input[name="q"]');
    if (!input) return;

    var overviewCard = document.getElementById('assets-overview-card');
    var resultsMeta = overviewCard && overviewCard.querySelector('.results-meta');

    // Restore focus to end of input if pre-filled by server
    if (input.value) {
        input.focus();
        var len = input.value.length;
        input.setSelectionRange(len, len);
    }

    input.addEventListener('input', function () {
        var term = input.value.trim().toLowerCase();
        var cards = document.querySelectorAll('.asset-card[data-search]');
        var visible = 0;

        cards.forEach(function (card) {
            var match = !term || card.dataset.search.indexOf(term) !== -1;
            card.style.display = match ? '' : 'none';
            if (match) visible++;
        });

        // Hide accordion groups that have no visible cards
        document.querySelectorAll('.asset-accordion').forEach(function (accordion) {
            var anyVisible = Array.from(accordion.querySelectorAll('.asset-card[data-search]'))
                .some(function (c) { return c.style.display !== 'none'; });
            accordion.style.display = anyVisible ? '' : 'none';
        });

        if (resultsMeta) {
            resultsMeta.textContent = visible + ' result' + (visible === 1 ? '' : 's');
        }
    });
})();
