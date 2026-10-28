(function () {
  const thread = document.querySelector(".chat-thread[data-message-url]");
  const form = document.getElementById("message-form");
  if (!thread || !form) return;

  const list = document.getElementById("message-list");
  const input = document.getElementById("message-body");
  const feedback = document.getElementById("chat-feedback");
  const submit = form.querySelector('button[type="submit"]');
  const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
  const knownIds = new Set(
    Array.from(list.querySelectorAll("[data-message-id]"), (element) => element.dataset.messageId)
  );

  function appendMessage(message) {
    if (knownIds.has(message.id)) {
      if (message.is_read) {
        const existing = list.querySelector('[data-message-id="' + message.id + '"] time');
        if (existing && !existing.textContent.includes("Dibaca")) {
          existing.textContent += " · Dibaca";
        }
      }
      return;
    }
    knownIds.add(message.id);

    const bubble = document.createElement("article");
    const isOwn = message.sender_id === Number(thread.closest("main").dataset.userId);
    bubble.className =
      "message-bubble max-w-[78%] rounded-2xl border border-line bg-surface px-3 py-2 shadow-sm [&>p]:[overflow-wrap:anywhere] [&>p]:whitespace-pre-wrap [&>p]:text-xs [&>p]:leading-normal [&>time]:mt-1 [&>time]:block [&>time]:text-right [&>time]:text-[0.65rem] [&>time]:text-muted" +
      (isOwn
        ? " message-own self-end border-brand bg-brand text-white [&>time]:text-[#c9e5d3]"
        : "");
    bubble.dataset.messageId = message.id;

    const body = document.createElement("p");
    body.textContent = message.body;
    const time = document.createElement("time");
    time.dateTime = message.sent_at;
    time.textContent = new Date(message.sent_at).toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
    });

    list.querySelector(".message-placeholder")?.remove();
    bubble.append(body, time);
    list.appendChild(bubble);
    list.scrollTop = list.scrollHeight;
  }

  async function refreshMessages() {
    try {
      const lastMessageTime = list.querySelector(".message-bubble:last-of-type time");
      const url = new URL(thread.dataset.messageUrl, window.location.origin);
      if (lastMessageTime) url.searchParams.set("after", lastMessageTime.dateTime);
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("Pesan gagal dimuat.");
      const data = await response.json();
      data.messages.forEach(appendMessage);
      feedback.textContent = "";
    } catch (error) {
      feedback.textContent = error.message || "Tidak dapat memuat pesan. Periksa koneksi lalu coba lagi.";
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!input.value.trim()) {
      feedback.textContent = "Pesan tidak boleh kosong.";
      input.focus();
      return;
    }

    submit.disabled = true;
    feedback.textContent = "";
    try {
      const response = await fetch(thread.dataset.sendUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({ body: input.value }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Pesan gagal dikirim. Periksa kembali isinya.");
      }
      appendMessage(data.message);
      input.value = "";
      input.focus();
      feedback.textContent = "";
    } catch (error) {
      feedback.textContent = error.message || "Tidak dapat mengirim pesan. Periksa koneksi lalu coba lagi.";
    } finally {
      submit.disabled = false;
    }
  });

  list.scrollTop = list.scrollHeight;
  window.setInterval(refreshMessages, 3000);
})();
