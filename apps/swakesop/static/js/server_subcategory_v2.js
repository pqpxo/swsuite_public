(function () {
    var SERVERS_SLUG = 'servers';

    var categorySelect = document.getElementById('category_id');
    var subcategoryWrap = document.getElementById('server-subcategory-wrap');
    var subcategorySelect = document.getElementById('server-subcategory-select');

    if (!categorySelect || !subcategoryWrap || !subcategorySelect) return;

    function getCategorySlug() {
        var opt = categorySelect.options[categorySelect.selectedIndex];
        if (!opt) return '';
        return (opt.text || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    }

    function isServers() {
        return getCategorySlug() === SERVERS_SLUG;
    }

    function updateSubcategoryVisibility() {
        if (isServers()) {
            subcategoryWrap.style.display = '';
        } else {
            subcategoryWrap.style.display = 'none';
            subcategorySelect.value = '';
        }
        updateGroupVisibility();
    }

    function updateGroupVisibility() {
        var selectedSub = subcategorySelect.value;
        var groups = document.querySelectorAll('[data-server-subcategory]');
        groups.forEach(function (g) {
            var sub = g.getAttribute('data-server-subcategory');
            if (!sub) return;
            if (!isServers()) {
                // category visibility script already hides these
                return;
            }
            if (sub === 'common') {
                g.hidden = false;
            } else if (!selectedSub) {
                g.hidden = true;
            } else {
                g.hidden = (sub !== selectedSub);
            }
        });
    }

    categorySelect.addEventListener('change', updateSubcategoryVisibility);
    subcategorySelect.addEventListener('change', updateGroupVisibility);

    // Re-apply subcategory filtering whenever category visibility script has run
    document.addEventListener('swakesop:category-visibility-updated', updateGroupVisibility);

    // Init on page load
    updateSubcategoryVisibility();
})();
