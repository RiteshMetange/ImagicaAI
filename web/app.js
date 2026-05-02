const messagesEl = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const clearButton = document.querySelector("#clear-chat");
const statusDot = document.querySelector("#status-dot");
const statusText = document.querySelector("#status-text");
const modelName = document.querySelector("#model-name");

const textarea = document.getElementById('message-input');

textarea.addEventListener('input', function() {
  this.style.height = 'auto'; // Reset height to recalculate
  this.style.height = (this.scrollHeight) + 'px'; // Set to scroll height
});

let history = [];
let configured = false;
let pexelsConfigured = false;
let openaiConfigured = false;
let busy = false;

function setStatus(state, text) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = text;
}

function setBusy(nextBusy) {
  busy = nextBusy;
  sendButton.disabled = busy || !configured;
  input.disabled = busy || !configured;
}

function scrollToLatest() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function readyMessage() {
  if (openaiConfigured && pexelsConfigured) {
    return "Ready. Ask me anything, try simple math, or ask for photos of mountains.";
  }

  if (pexelsConfigured) {
    return "Ready for basic chat and Pexels. Try hi, 24 * 7, 10 km to miles, or photos of mountains.";
  }

  if (openaiConfigured) {
    return "Ready for general chat. Pexels image search needs PEXELS_API_KEY.";
  }

  return "Ready for basic chat. Add OPENAI_API_KEY for fuller replies or PEXELS_API_KEY for images.";
}

function readyStatusText() {
  if (openaiConfigured && pexelsConfigured) {
    return "Chat + Pexels ready";
  }

  if (pexelsConfigured) {
    return "Basic chat + Pexels";
  }

  if (openaiConfigured) {
    return "Chat ready";
  }

  return "Basic chat ready";
}

function appendMessage(role, content, images = []) {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : role === "assistant" ? "AI Bot" : "Imagica";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  wrapper.append(label, bubble);

  if (images.length > 0) {
    const grid = document.createElement("div");
    grid.className = "image-grid";

    for (const image of images) {
      const card = document.createElement("a");
      card.className = "image-card";
      card.href = image.sourceUrl || image.imageUrl;
      card.target = "_blank";
      card.rel = "noopener noreferrer";

      const img = document.createElement("img");
      img.src = image.thumbnailUrl || image.imageUrl;
      img.alt = image.alt || "Pexels image";
      img.loading = "lazy";

      const meta = document.createElement("span");
      meta.className = "image-meta";
      meta.textContent = `Photo by ${image.photographer || "Pexels"}`;

      card.append(img, meta);
      grid.appendChild(card);
    }

    wrapper.appendChild(grid);
  }

  messagesEl.appendChild(wrapper);
  scrollToLatest();
}

function autosizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 170)}px`;
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();

    configured = Boolean(status.configured);
    pexelsConfigured = Boolean(status.pexelsConfigured);
    openaiConfigured = Boolean(status.openaiConfigured);
    modelName.textContent = status.model || "Model";

    if (configured) {
      setStatus("ready", readyStatusText());
      input.disabled = false;
      sendButton.disabled = false;
      appendMessage("assistant", readyMessage());
    } else {
      setStatus("missing", "Not ready");
      setBusy(false);
      appendMessage("system", "The server is not ready.");
    }
  } catch (error) {
    configured = false;
    setStatus("missing", "Server offline");
    setBusy(false);
    appendMessage("system", "The local server is not responding.");
  }
}

async function sendMessage(message) {
  appendMessage("user", message);
  setBusy(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Request failed.");
    }

    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: payload.reply });
    appendMessage("assistant", payload.reply, payload.images || []);
  } catch (error) {
    appendMessage("system", error.message);
  } finally {
    setBusy(false);
    input.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();

  if (!message || busy || !configured) {
    return;
  }

  input.value = "";
  autosizeInput();
  sendMessage(message);
});

input.addEventListener("input", autosizeInput);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

clearButton.addEventListener("click", () => {
  history = [];
  messagesEl.textContent = "";
  if (configured) {
    appendMessage("assistant", readyMessage());
  } else {
    appendMessage("system", "The server is not ready.");
  }
  input.focus();
});

loadStatus();
