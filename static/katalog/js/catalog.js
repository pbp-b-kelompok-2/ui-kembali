// Catalog page: start with the filter panel folded on phones so the results
// are visible first. Desktop keeps it open (the markup ships with `open`).
(function () {
  const panel = document.getElementById("filter-panel");
  if (panel && window.matchMedia("(max-width: 1023px)").matches) {
    panel.open = false;
  }
})();
