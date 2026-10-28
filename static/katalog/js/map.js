// Detail page map (Leaflet + OpenStreetMap tiles). The server decides how
// precise the point is: logged-in users get the exact pin (data-exact="true"),
// anonymous users get coordinates rounded to ~100 m, drawn as an area circle.
(function () {
  const el = document.getElementById("item-map");
  if (!el || !window.L) return;

  const point = [parseFloat(el.dataset.lat), parseFloat(el.dataset.lng)];
  const exact = el.dataset.exact === "true";
  // scrollWheelZoom off: scrolling down the page shouldn't zoom the map.
  const map = L.map(el, { scrollWheelZoom: false }).setView(point, exact ? 17 : 16);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    // OSM's tile servers block requests without a Referer, and Django's
    // default Referrer-Policy (same-origin) sends none to other sites.
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  if (exact) {
    // Leaflet treats a string popup as HTML; a text node keeps user input inert.
    const label = document.createElement("span");
    label.textContent = el.dataset.label;
    L.marker(point).addTo(map).bindPopup(label);
  } else {
    L.circle(point, { radius: 250, color: "#257a47", fillOpacity: 0.15 }).addTo(map);
  }
})();
