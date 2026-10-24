// Shared item modal (<dialog id="item-modal">).
// - Opens whenever HTMX swaps content into #modal-body (Edit / Pasang barang,
//   and a 422 form that the server retargets there).
// - Closes optimistically as soon as the form is sent; if the server answers
//   422 the form comes back into #modal-body and the modal reopens.
(function () {
  // HTMX 2 does not swap 4xx responses by default. Let 422 (form errors)
  // through; other errors stay unswapped and only fire toasts.
  htmx.config.responseHandling.unshift({ code: "422", swap: true, error: false });

  const modal = document.getElementById("item-modal");
  const body = document.getElementById("modal-body");
  if (!modal || !body) return;

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail.target === body && !modal.open) {
      modal.showModal();
      const first = body.querySelector("input:not([type=hidden]), textarea, select");
      if (first) first.focus();
    }
  });

  document.body.addEventListener("htmx:beforeRequest", function (event) {
    if (event.detail.elt.id === "item-form") modal.close();
  });

  // Network or server failure: put the (still filled-in) form back on screen.
  document.body.addEventListener("htmx:responseError", function (event) {
    if (event.detail.elt.id === "item-form") modal.showModal();
  });
  document.body.addEventListener("htmx:sendError", function (event) {
    if (event.detail.elt.id === "item-form") modal.showModal();
  });

  modal.addEventListener("click", function (event) {
    // [data-modal-close] buttons, or a click on the backdrop itself.
    if (event.target.closest("[data-modal-close]") || event.target === modal) {
      modal.close();
    }
  });
})();
