(function () {
    var SERVERS_SLUG = 'servers';
    var SUBCATEGORY_PREFIXES = ['physical_host', 'hypervisor', 'virtual_machine', 'lxc_container', 'docker_host'];

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
        var selectedSub = subcategorySelect.value; // e.g. "physical_host" or ""
        var groups = document.querySelectorAll('[data-server-subcategory]');
        groups.forEach(function (g) {
            var sub = g.getAttribute('data-server-subcategory');
            if (!sub) return; // not a server group
            if (!isServers()) {
                // handled by existing category visibility logic
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

    // Init on page load
    updateSubcategoryVisibility();
})();
