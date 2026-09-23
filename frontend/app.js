const state = { chats: [], active: null, chunkPage: 1, streaming: false };
const $ = (id) => document.getElementById(id);

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Unable to connect to the server.");
  }
  return response.json();
}

function showNotice(message) {
  $("notice").textContent = message;
  $("notice").classList.remove("hidden");
}

function clearNotice() { $("notice").classList.add("hidden"); }

async function loadChats() {
  state.chats = await api("/api/chats");
  renderChatList();
  if (!state.active && state.chats.length) await selectChat(state.chats[0].chat_id);
  if (!state.active) await createChat();
}

function renderChatList() {
  $("chat-list").innerHTML = state.chats.map((chat) => `
    <div class="chat-item ${state.active?.chat_id === chat.chat_id ? "active" : ""}">
      <button data-chat="${chat.chat_id}">
        <span class="chat-title">${escapeHtml(chat.title)}</span>
        <span class="chat-document">${escapeHtml(chat.document?.name || "No document yet")}</span>
      </button>
    </div>`).join("");
  document.querySelectorAll("[data-chat]").forEach((button) => {
    button.addEventListener("click", () => selectChat(button.dataset.chat));
  });
}

async function createChat() {
  state.active = await api("/api/chats", { method: "POST" });
  state.chats.push({ chat_id: state.active.chat_id, title: state.active.title, document: null });
  state.chunkPage = 1;
  renderChatList();
  render();
}

async function selectChat(chatId) {
  state.active = await api(`/api/chats/${chatId}`);
  state.chunkPage = 1;
  renderChatList();
  render();
}

function render() {
  $("chat-title").textContent = state.active.title;
  $("message-list").innerHTML = state.active.messages.map(renderMessage).join("");
  $("message-list").classList.toggle("hidden", !state.active.messages.length);
  $("empty-state").classList.toggle("hidden", !!state.active.document || !!state.active.messages.length);
  renderDocument();
  $("content").scrollTop = $("content").scrollHeight;
}

function renderMessage(message) {
  const sources = message.sources?.length ? `
    <details class="sources"><summary>Sources · ${message.sources.length} retrieved chunks</summary>
      ${message.sources.map((source) => `<div class="source-item"><strong>Chunk ${source.number}</strong> · ${escapeHtml(source.text)}</div>`).join("")}
    </details>` : "";
  return `<article class="message ${message.role}">
    <div class="message-meta">${message.role === "user" ? "You" : "Archive"}</div>
    <div class="message-body">${escapeHtml(message.content)}</div>${sources}
  </article>`;
}

function renderDocument() {
  const document = state.active.document;
  $("document-card").classList.toggle("hidden", !document);
  $("chunks-section").classList.toggle("hidden", !document);
  if (!document) return;
  $("document-card").innerHTML = `
    <div class="document-name">${escapeHtml(document.name)}</div>
    <div class="document-meta">${escapeHtml(document.content_type)} · ${formatBytes(document.size)}</div>
    <div class="status">✓ ${document.status === "ready" ? "Document processed" : document.status}</div>`;
  $("chunk-count").textContent = `${document.chunk_count} chunks`;
  loadChunks();
}

async function loadChunks() {
  const data = await api(`/api/chats/${state.active.chat_id}/chunks?page=${state.chunkPage}&page_size=8`);
  $("chunk-list").innerHTML = data.items.map((chunk) => `
    <article class="chunk">
      <div class="chunk-number">Chunk ${chunk.number}</div>
      <div class="chunk-text">${escapeHtml(chunk.text)}</div>
      <div class="chunk-source">${escapeHtml(chunk.source)}${chunk.metadata.page ? ` · Page ${chunk.metadata.page}` : ""}</div>
    </article>`).join("");
  $("page-label").textContent = `${data.page} / ${data.pages}`;
  $("previous-page").disabled = data.page <= 1;
  $("next-page").disabled = data.page >= data.pages;
}

async function upload(file) {
  if (!file || !state.active) return;
  clearNotice();
  let replace = false;
  if (state.active.document) {
    replace = confirm("This chat already has a document. Choose OK to replace it, or Cancel to create a new chat.");
    if (!replace) {
      await createChat();
      return upload(file);
    }
  }
  const form = new FormData();
  form.append("file", file);
  if (replace) form.append("replace", "true");
  $("document-card").classList.remove("hidden");
  $("document-card").innerHTML = `<div class="document-name">${escapeHtml(file.name)}</div><div class="document-meta">${escapeHtml(file.type || "Document")} · ${formatBytes(file.size)}</div><div class="status">Processing document…</div>`;
  try {
    state.active = await api(`/api/chats/${state.active.chat_id}/document`, { method: "POST", body: form });
    const index = state.chats.findIndex((chat) => chat.chat_id === state.active.chat_id);
    state.chats[index] = { chat_id: state.active.chat_id, title: state.active.title, document: state.active.document };
    renderChatList();
    render();
  } catch (error) { showNotice(error.message); render(); }
}

async function sendMessage(event) {
  event.preventDefault();
  if (state.streaming) return;
  const question = $("question").value.trim();
  if (!question) return showNotice("Enter a question.");
  if (!state.active.document) return showNotice("Upload a document before asking questions.");
  clearNotice();
  state.streaming = true;
  $("question").disabled = true;
  $("composer").querySelector("button").disabled = true;
  $("question").value = "";
  state.active.messages.push({ role: "user", content: question });
  state.active.messages.push({ role: "assistant", content: "", sources: [] });
  render();
  const assistant = state.active.messages.at(-1);
  try {
    const response = await fetch(`/api/chats/${state.active.chat_id}/messages`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question })
    });
    if (!response.ok) throw new Error((await response.json()).detail || "Unable to connect to the server.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const raw of events) {
        const name = raw.match(/^event: (.+)$/m)?.[1];
        const data = JSON.parse(raw.match(/^data: (.+)$/m)?.[1] || "{}");
        if (name === "token") assistant.content += data;
        if (name === "sources") assistant.sources = data;
        if (name === "error") throw new Error(data.message);
        renderMessagesOnly();
      }
    }
  } catch (error) { showNotice(error.message); }
  state.streaming = false;
  $("question").disabled = false;
  $("composer").querySelector("button").disabled = false;
  renderMessagesOnly();
}

function renderMessagesOnly() {
  $("message-list").innerHTML = state.active.messages.map((message, index) => {
    const html = renderMessage(message);
    return index === state.active.messages.length - 1 && state.streaming
      ? html.replace('class="message assistant"', 'class="message assistant streaming"') : html;
  }).join("");
  $("content").scrollTop = $("content").scrollHeight;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

$("new-chat").addEventListener("click", createChat);
$("empty-upload").addEventListener("click", () => $("file-input").click());
$("upload-button").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => upload(event.target.files[0]));
$("dropzone").addEventListener("click", () => $("file-input").click());
$("dropzone").addEventListener("dragover", (event) => { event.preventDefault(); $("dropzone").classList.add("dragover"); });
$("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("dragover"));
$("dropzone").addEventListener("drop", (event) => { event.preventDefault(); $("dropzone").classList.remove("dragover"); upload(event.dataTransfer.files[0]); });
$("composer").addEventListener("submit", sendMessage);
$("previous-page").addEventListener("click", () => { state.chunkPage -= 1; loadChunks(); });
$("next-page").addEventListener("click", () => { state.chunkPage += 1; loadChunks(); });
$("delete-chat").addEventListener("click", async () => {
  if (!state.active || !confirm("Delete this conversation?")) return;
  await api(`/api/chats/${state.active.chat_id}`, { method: "DELETE" });
  state.active = null;
  await loadChats();
});
loadChats().catch((error) => showNotice(error.message));
