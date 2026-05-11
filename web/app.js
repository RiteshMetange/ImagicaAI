const messagesEl = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const clearButton = document.querySelector("#clear-chat");
const statusDot = document.querySelector("#status-dot");
const statusText = document.querySelector("#status-text");
const modelName = document.querySelector("#model-name");
const providerSelect = document.querySelector("#provider-select");
const providerHint = document.querySelector("#provider-hint");

const PROVIDER_STORAGE_KEY = "imagica.llmProvider";

let history = [];
let configured = false;
let pexelsConfigured = false;
let openaiConfigured = false;
let geminiConfigured = false;
let llmProviders = [];
let selectedProvider = loadStoredProvider();
let busy = false;

function loadStoredProvider() {
  try {
    return localStorage.getItem(PROVIDER_STORAGE_KEY) || "openai";
  } catch (error) {
    return "openai";
  }
}

function saveStoredProvider(providerId) {
  try {
    localStorage.setItem(PROVIDER_STORAGE_KEY, providerId);
  } catch (error) {
    // Preference persistence is helpful, but chat should still work without it.
  }
}

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

function getProviderInfo(providerId = selectedProvider) {
  const provider = llmProviders.find((item) => item.id === providerId);
  if (provider) {
    return provider;
  }

  const label = providerId === "gemini" ? "Gemini" : "OpenAI";
  return {
    id: providerId,
    label,
    configured: false,
    model: "",
  };
}

function hasAnyLlmProvider() {
  return llmProviders.some((provider) => provider.configured);
}

function setProviderOptions(providers) {
  providerSelect.textContent = "";

  for (const provider of providers) {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent = provider.configured
      ? provider.label
      : `${provider.label} (missing key)`;
    providerSelect.appendChild(option);
  }

  if (!providers.some((provider) => provider.id === selectedProvider)) {
    selectedProvider = providers[0]?.id || "openai";
  }

  providerSelect.value = selectedProvider;
}

function updateProviderUi() {
  const provider = getProviderInfo();
  const model = provider.model || "local fallback";
  modelName.textContent = `${provider.label} - ${model}`;
  providerHint.textContent = provider.configured
    ? `Using ${provider.label}`
    : `${provider.label} key missing`;

  if (!configured) {
    setStatus("missing", "Server offline");
    return;
  }

  setStatus("ready", readyStatusText());
}

function readyMessage() {
  const provider = getProviderInfo();

  if (provider.configured && pexelsConfigured) {
    return `Ready. ${provider.label} handles AI replies, and Pexels handles image search.`;
  }

  if (provider.configured) {
    return `Ready. ${provider.label} handles AI replies. Pexels image search needs PEXELS_API_KEY.`;
  }

  if (hasAnyLlmProvider() && pexelsConfigured) {
    return `${provider.label} is missing a key, so AI replies will fall back to another configured provider. Pexels image search is ready.`;
  }

  if (pexelsConfigured) {
    return `Ready for basic chat and Pexels. Add ${provider.label.toUpperCase()}_API_KEY for fuller AI replies.`;
  }

  return "Ready for basic chat. Add OPENAI_API_KEY, GEMINI_API_KEY, or PEXELS_API_KEY for more features.";
}

function readyStatusText() {
  const provider = getProviderInfo();

  if (provider.configured && pexelsConfigured) {
    return `${provider.label} + Pexels ready`;
  }

  if (provider.configured) {
    return `${provider.label} ready`;
  }

  if (hasAnyLlmProvider() && pexelsConfigured) {
    return `${provider.label} missing, fallback ready`;
  }

  if (hasAnyLlmProvider()) {
    return `${provider.label} missing, fallback ready`;
  }

  if (pexelsConfigured) {
    return "Basic chat + Pexels";
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
    geminiConfigured = Boolean(status.geminiConfigured);
    llmProviders = status.llmProviders || [
      {
        id: "openai",
        label: "OpenAI",
        configured: openaiConfigured,
        model: status.model || "",
      },
      {
        id: "gemini",
        label: "Gemini",
        configured: geminiConfigured,
        model: "",
      },
    ];

    if (!llmProviders.some((provider) => provider.id === selectedProvider)) {
      selectedProvider = status.defaultProvider || "openai";
      saveStoredProvider(selectedProvider);
    }

    setProviderOptions(llmProviders);
    updateProviderUi();

    if (configured) {
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
      body: JSON.stringify({ message, history, provider: selectedProvider }),
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

providerSelect.addEventListener("change", () => {
  selectedProvider = providerSelect.value;
  saveStoredProvider(selectedProvider);
  updateProviderUi();
  appendMessage("system", `AI responses will use ${getProviderInfo().label}.`);
  input.focus();
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
