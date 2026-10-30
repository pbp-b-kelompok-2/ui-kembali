(function () {
  const button = document.querySelector("[data-chat-start-url]");
  if (!button) return;

  const feedback = document.getElementById("chat-start-feedback");
  button.addEventListener("click", async function () {
    button.disabled = true;
    feedback.textContent = "";
    try {
      const response = await fetch(button.dataset.chatStartUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": button.dataset.csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({}),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Percakapan gagal dibuat.");
      }
      window.location.assign(data.url);
    } catch (error) {
      feedback.textContent = error.message || "Tidak dapat terhubung ke server. Coba lagi.";
      button.disabled = false;
    }
  });
})();
