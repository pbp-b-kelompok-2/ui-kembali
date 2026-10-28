// Optimistic UI: an element with data-optimistic-hide="<selector>" hides that
// target as soon as its request starts, and shows it again if the request
// fails. Used by "Hapus": the card disappears instantly, and the server's
// 204 + Undo toast keeps it hidden (still in the page, so Undo can swap it back).
(function () {
  function targetOf(elt) {
    const selector = elt.getAttribute("data-optimistic-hide");
    return selector ? document.querySelector(selector) : null;
  }

  document.body.addEventListener("htmx:beforeRequest", function (event) {
    const target = targetOf(event.detail.elt);
    if (target) target.hidden = true;
  });

  function rollback(event) {
    const target = targetOf(event.detail.elt);
    if (target) target.hidden = false;
  }
  ["htmx:responseError", "htmx:sendError"].forEach(function (name) {
    document.body.addEventListener(name, rollback);
  });
})();
