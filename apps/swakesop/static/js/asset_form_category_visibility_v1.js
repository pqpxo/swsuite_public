// ## version 1
(function () {
  const categorySelect = document.querySelector('[data-role="asset-category"]');
  const fields = Array.from(document.querySelectorAll('.category-scoped-field'));
  const helper = document.querySelector('[data-role="category-helper-text"]');

  if (!categorySelect || !fields.length) {
    return;
  }

  const normalise = (value) => String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-');

  function getSelectedCategoryTokens() {
    const option = categorySelect.options[categorySelect.selectedIndex];
    const rawValue = categorySelect.value;
    const optionText = option ? option.textContent : '';
    const tokens = new Set([
      normalise(rawValue),
      normalise(optionText),
      normalise(optionText).replace(/-+/g, ' '),
    ]);
    return Array.from(tokens).filter(Boolean);
  }

  function matchesScope(scope, selectedTokens) {
    if (!scope) return true;
    const parts = String(scope)
      .split(/[|,]/)
      .map((part) => normalise(part))
      .filter(Boolean);

    if (!parts.length) return true;
    if (parts.includes('all') || parts.includes('universal') || parts.includes('*')) return true;
    if (!selectedTokens.length) return false;
    return parts.some((part) => selectedTokens.includes(part));
  }

  function updateVisibility() {
    const selectedTokens = getSelectedCategoryTokens();
    let visibleCount = 0;

    fields.forEach((field) => {
      const scope = field.getAttribute('data-category-scope') || 'all';
      const show = matchesScope(scope, selectedTokens);
      field.hidden = !show;
      field.classList.toggle('is-hidden-by-category', !show);
      if (show) visibleCount += 1;
    });

    if (helper) {
      if (!selectedTokens.length) {
        helper.textContent = 'Select a category to show only the matching fields.';
      } else if (!visibleCount) {
        helper.textContent = 'No additional category-specific fields are defined for this category yet.';
      } else {
        helper.textContent = 'Only the fields for the selected category are shown.';
      }
    }
  }

  categorySelect.addEventListener('change', updateVisibility);
  updateVisibility();
})();
