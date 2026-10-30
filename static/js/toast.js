// Shared toasts. Server side: send the header
//   HX-Trigger: {"toast": {"msg": "Barang disimpan", "level": "success"}}
// Client side: window.showToast("pesan", "error").
// Optional Undo: add "undo": "<url>" and "target": "<selector>" to the toast;
// the button POSTs to the url and swaps the response over the target.
(function () {
  const DURATION_MS = 4000;
  const UNDO_DURATION_MS = 8000; // give people time to reach the Undo button
  const LEVELS = ["success", "error", "info"];

  function undoButton(toast, url, target) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toast-action";
    button.textContent = "Urungkan";
    button.addEventListener("click", function () {
      button.disabled = true;
      // hx-headers on <body> carries the CSRF token; htmx.ajax doesn't read it.
      const headers = JSON.parse(document.body.getAttribute("hx-headers") || "{}");
      htmx.ajax("POST", url, { target: target, swap: "outerHTML", headers: headers });
      toast.remove();
    });
    return button;
  }

  function showToast(msg, level, undo) {
    const stack = document.getElementById("toast-stack");
    if (!stack || !msg) return;

    const toast = document.createElement("div");
    toast.className = "toast toast-" + (LEVELS.includes(level) ? level : "info");
    toast.textContent = msg;
    const canUndo = undo && undo.url && document.querySelector(undo.target);
    if (canUndo) toast.appendChild(undoButton(toast, undo.url, undo.target));
    stack.appendChild(toast);

    setTimeout(function () {
      toast.classList.add("toast-leave");
      toast.addEventListener("animationend", function () { toast.remove(); });
    }, canUndo ? UNDO_DURATION_MS : DURATION_MS);
  }

  window.showToast = showToast;

  document.body.addEventListener("toast", function (event) {
    const detail = event.detail || {};
    showToast(detail.msg, detail.level, { url: detail.undo, target: detail.target });
  });

  // Network errors or 5xx that the view didn't turn into a toast.
  const ERRORS = {
    403: "Kamu tidak punya akses untuk aksi ini.",
    404: "Data tidak ditemukan atau sudah berubah. Muat ulang halaman.",
  };
  document.body.addEventListener("htmx:responseError", function (event) {
    const xhr = event.detail.xhr;
    if (!xhr.getResponseHeader("HX-Trigger")) {
      showToast(ERRORS[xhr.status] || "Terjadi kesalahan, coba lagi.", "error");
    }
  });
  document.body.addEventListener("htmx:sendError", function () {
    showToast("Tidak dapat terhubung ke server.", "error");
  });
})();
