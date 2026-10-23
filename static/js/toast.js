// Shared toasts. Server side: send the header
//   HX-Trigger: {"toast": {"msg": "Barang disimpan", "level": "success"}}
// Client side: window.showToast("pesan", "error").
(function () {
  const DURATION_MS = 4000;
  const LEVELS = ["success", "error", "info"];

  function showToast(msg, level) {
    const stack = document.getElementById("toast-stack");
    if (!stack || !msg) return;

    const toast = document.createElement("div");
    toast.className = "toast toast-" + (LEVELS.includes(level) ? level : "info");
    toast.textContent = msg;
    stack.appendChild(toast);

    setTimeout(function () {
      toast.classList.add("toast-leave");
      toast.addEventListener("animationend", function () { toast.remove(); });
    }, DURATION_MS);
  }

  window.showToast = showToast;

  document.body.addEventListener("toast", function (event) {
    const detail = event.detail || {};
    showToast(detail.msg, detail.level);
  });

  // Network errors or 5xx that the view didn't turn into a toast.
  document.body.addEventListener("htmx:responseError", function (event) {
    if (!event.detail.xhr.getResponseHeader("HX-Trigger")) {
      showToast("Terjadi kesalahan, coba lagi.", "error");
    }
  });
  document.body.addEventListener("htmx:sendError", function () {
    showToast("Tidak dapat terhubung ke server.", "error");
  });
})();
