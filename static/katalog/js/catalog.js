// Catalog page: start with the filter panel folded on phones so the results
// are visible first. Desktop keeps it open (the markup ships with `open`).
(function () {
  const panel = document.getElementById("filter-panel");
  if (panel && window.matchMedia("(max-width: 1023px)").matches) {
    panel.open = false;
  }
})();

// "Gunakan lokasiku": put the browser's position in the hidden lat/lng inputs
// and re-run the filter. Choosing a named place afterwards clears them, since
// a named place and "my location" are two ways to pick the same centre.
// Picking a centre also switches the sort to "Terdekat": the sort <select>
// always submits a value, and the server lets an explicit sort win.
(function () {
  const form = document.getElementById("filter-form");
  const button = document.getElementById("use-my-location");
  if (!form || !button) return;
  const lat = form.elements.lat;
  const lng = form.elements.lng;
  const sortByDistance = function () { form.elements.sort.value = "distance"; };

  button.addEventListener("click", function () {
    if (!navigator.geolocation) {
      window.showToast("Browser ini tidak bisa membaca lokasi.", "error");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        lat.value = pos.coords.latitude.toFixed(5);
        lng.value = pos.coords.longitude.toFixed(5);
        form.elements.near.value = "";
        sortByDistance();
        htmx.trigger(form, "submit");
      },
      function () {
        window.showToast("Izin lokasi ditolak.", "error");
      },
      { timeout: 10000 }
    );
  });

  form.elements.near.addEventListener("change", function () {
    lat.value = "";
    lng.value = "";
    if (form.elements.near.value) sortByDistance();
  });
})();
