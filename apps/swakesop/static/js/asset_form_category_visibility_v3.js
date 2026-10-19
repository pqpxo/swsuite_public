/* ## version 3 */
(function () {
  const categorySelect = document.getElementById('category_id');
  const groups = Array.from(document.querySelectorAll('.category-field-group'));
  const emptyNotice = document.getElementById('category-field-empty');

  if (!categorySelect || !groups.length) return;

  const scopeAliases = {
    servers: 'servers',
    server: 'servers',
    raspberry_pi: 'raspberry_pi',
    'raspberry pi': 'raspberry_pi',
    single_board_computers: 'raspberry_pi',
    'single board computers': 'raspberry_pi',
    network_equipment: 'network_equipment',
    'network equipment': 'network_equipment',
    cameras: 'cameras',
    camera: 'cameras',
    power: 'power',
    storage: 'storage',
    laptops: 'laptops',
    laptop: 'laptops',
    lxc_vms: 'lxc_vms',
    'lxc & vms': 'lxc_vms',
    lxc_and_vms: 'lxc_vms',
    vms: 'lxc_vms',
    vm: 'lxc_vms',
    cables_adapters: 'cables_adapters',
    'cables & adapters': 'cables_adapters',
    iot_devices: 'iot_devices',
    'iot devices': 'iot_devices',
    media_gaming: 'media_gaming',
    'media & gaming': 'media_gaming',
    mobile_tablets: 'mobile_tablets',
    'mobile & tablets': 'mobile_tablets',
    pcs_workstations: 'pcs_workstations',
    'pcs & workstations': 'pcs_workstations',
    pcs: 'pcs_workstations',
    peripherals: 'peripherals'
  };

  function slugify(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function selectedScope() {
    const option = categorySelect.options[categorySelect.selectedIndex];
    if (!option) return '';
    const slug = slugify(option.textContent || option.innerText || '');
    return scopeAliases[slug] || slug;
  }

  function updateVisibility() {
    const scope = selectedScope();
    let visibleCount = 0;

    groups.forEach((group) => {
      const groupScope = (group.dataset.fieldScope || '').trim();
      const show = groupScope === 'universal' || (!!scope && groupScope === scope);
      group.hidden = !show;
      if (show) visibleCount += 1;
    });

    if (emptyNotice) {
      emptyNotice.hidden = visibleCount > 0 || !scope;
    }
  }

  categorySelect.addEventListener('change', updateVisibility);
  window.requestAnimationFrame(updateVisibility);
})();
