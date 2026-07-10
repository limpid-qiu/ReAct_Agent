const state = {
  conversationId: null,
  messages: [],
};

const $ = (selector) => document.querySelector(selector);

function headers(includeJson = true) {
  const apiKey = $("#apiKey").value.trim();
  const result = {
    "X-User-ID": $("#userId").value.trim() || "demo_user",
    "X-Tenant-ID": $("#tenantId").value.trim() || "demo_tenant",
  };

  if (includeJson) {
    result["Content-Type"] = "application/json";
  }

  const knowledgeBaseInput = $("#knowledgeBaseId");
  const knowledgeBaseId = knowledgeBaseInput?.value.trim();

  if (knowledgeBaseId) {
    result["X-Knowledge-Base-ID"] = knowledgeBaseId;
  }

  if (apiKey) {
    result["X-API-Key"] = apiKey;
  }

  return result;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.style.display = "block";
  window.setTimeout(() => {
    toast.style.display = "none";
  }, 3600);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...headers(options.body !== undefined && !(options.body instanceof FormData)),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function switchView(name) {
  document.querySelectorAll(".view").forEach((node) => {
    node.classList.toggle("active", node.id === name);
  });
  document.querySelectorAll(".tabs button").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === name);
  });

  if (name === "knowledge") loadKnowledge();
  if (name === "conversations") loadConversations();
  if (name === "monitoring") loadMonitor();
  if (name === "logs") loadLogs();
}

function renderMessages() {
  const box = $("#messages");
  box.innerHTML = state.messages
    .map(
      (message) =>
        `<div class="message ${message.role}">${escapeHtml(message.content)}</div>`,
    )
    .join("");
  box.scrollTop = box.scrollHeight;
  $("#chatMeta").textContent = state.conversationId || "新会话";
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $("#query");
  const query = input.value.trim();

  if (!query) return;

  input.value = "";
  state.messages.push({ role: "user", content: query });
  state.messages.push({ role: "assistant", content: "思考中..." });
  renderMessages();

  try {
    const data = await request("/api/chat/", {
      method: "POST",
      body: JSON.stringify({
        query,
        conversation_id: state.conversationId,
        history: state.messages
          .slice(0, -1)
          .filter((item) => item.role === "user" || item.role === "assistant"),
      }),
    });

    state.conversationId = data.conversation_id;
    state.messages[state.messages.length - 1] = {
      role: "assistant",
      content: data.answer,
    };
    renderMessages();
  } catch (error) {
    state.messages[state.messages.length - 1] = {
      role: "assistant",
      content: `请求失败：${error.message}`,
    };
    renderMessages();
  }
}

async function loadConversations() {
  try {
    const data = await request("/api/conversations?limit=30");
    const list = $("#conversationList");
    list.innerHTML = data.conversations
      .map(
        (item) => `
          <div class="list-item" data-id="${item.id}">
            <strong>${escapeHtml(item.title || item.id)}</strong>
            <div class="muted">${item.message_count} 条消息</div>
            <div class="muted">${formatTime(item.updated_at)}</div>
          </div>
        `,
      )
      .join("");

    list.querySelectorAll(".list-item").forEach((node) => {
      node.addEventListener("click", () => loadConversationDetail(node.dataset.id));
    });
  } catch (error) {
    showToast(`会话加载失败：${error.message}`);
  }
}

async function loadConversationDetail(id) {
  try {
    const data = await request(`/api/conversations/${encodeURIComponent(id)}`);
    $("#conversationDetail").innerHTML = `
      <h3>${escapeHtml(data.title || data.id)}</h3>
      <p class="muted">${data.id}</p>
      ${data.messages
        .map(
          (message) => `
            <div class="message ${message.role}">
              <div class="muted">${message.role} · ${formatTime(message.created_at)}</div>
              ${escapeHtml(message.content)}
            </div>
          `,
        )
        .join("")}
    `;
  } catch (error) {
    showToast(`会话详情加载失败：${error.message}`);
  }
}

async function loadMonitor() {
  try {
    const [health, overview, metrics] = await Promise.all([
      request("/api/health"),
      request("/api/monitoring/overview"),
      fetch("/metrics").then((response) => response.text()),
    ]);

    $("#health").textContent = `${health.service}: ${health.status}`;
    $("#statGrid").innerHTML = Object.entries(overview.counts)
      .map(
        ([key, value]) => `
          <div class="stat">
            <span>${labelFor(key)}</span>
            <strong>${value}</strong>
          </div>
        `,
      )
      .join("");

    $("#toolCalls").innerHTML = overview.recent_tools.length
      ? overview.recent_tools
          .map(
            (tool) => `
              <div class="tool-row">
                <strong>${escapeHtml(tool.tool_name)}</strong>
                <span>${escapeHtml(tool.status)}</span>
                <span>${tool.latency_ms ?? "-"} ms</span>
                <span class="muted">${formatTime(tool.created_at)}</span>
              </div>
            `,
          )
          .join("")
      : '<div class="muted">暂无工具调用记录</div>';

    $("#metrics").textContent = metrics
      .split("\n")
      .filter((line) => line && !line.startsWith("#"))
      .slice(0, 80)
      .join("\n");
  } catch (error) {
    showToast(`监控加载失败：${error.message}`);
  }
}

async function loadLogs() {
  try {
    const data = await request("/api/monitoring/logs?limit=120");
    $("#logLines").textContent = data.lines.join("\n") || "暂无日志";
  } catch (error) {
    showToast(`日志加载失败：${error.message}`);
  }
}


async function loadKnowledge() {
  await Promise.all([loadKnowledgeBases(), loadDocuments(), loadTasks()]);
}

async function loadKnowledgeBases() {
  try {
    const data = await request("/api/knowledge/bases?limit=30");
    const currentId = getKnowledgeBaseId();
    const list = $("#baseList");
    list.innerHTML = data.knowledge_bases.length
      ? data.knowledge_bases
          .map(
            (base) => `
              <div class="compact-item ${base.id === currentId ? "active" : ""}" data-id="${base.id}">
                <strong>${escapeHtml(base.name)}</strong>
                <div class="muted">${escapeHtml(base.id)}</div>
                <div class="muted">${escapeHtml(base.description || "无描述")}</div>
              </div>
            `,
          )
          .join("")
      : '<div class="muted">暂无知识库，默认知识库会在首次访问时自动创建</div>';

    list.querySelectorAll(".compact-item").forEach((node) => {
      node.addEventListener("click", () => {
        $("#knowledgeBaseId").value = node.dataset.id;
        loadKnowledge();
      });
    });
  } catch (error) {
    showToast(`知识库列表加载失败：${error.message}`);
  }
}

async function createKnowledgeBase(event) {
  event.preventDefault();
  const name = $("#baseName").value.trim();
  const description = $("#baseDescription").value.trim();

  if (!name) {
    showToast("请输入知识库名称");
    return;
  }

  try {
    const data = await request("/api/knowledge/bases", {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    });
    $("#knowledgeBaseId").value = data.knowledge_base.id;
    $("#baseName").value = "";
    $("#baseDescription").value = "";
    showToast("知识库已创建");
    loadKnowledge();
  } catch (error) {
    showToast(`创建知识库失败：${error.message}`);
  }
}

async function uploadKnowledgeFile(event) {
  event.preventDefault();
  const fileInput = $("#knowledgeFile");
  const file = fileInput.files[0];

  if (!file) {
    showToast("请选择 txt、pdf 或 docx 文件");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  $("#uploadResult").textContent = "正在上传并创建入库任务...";

  try {
    const data = await request("/api/knowledge/documents/upload", {
      method: "POST",
      body: formData,
    });
    fileInput.value = "";
    $("#uploadResult").textContent = `${data.message} task_id=${data.task_id}`;
    showToast("上传成功，后台正在入库");
    loadKnowledge();
  } catch (error) {
    $("#uploadResult").textContent = "";
    showToast(`上传失败：${error.message}`);
  }
}

async function loadDocuments() {
  try {
    const data = await request("/api/knowledge/documents?limit=30");
    $("#documentList").innerHTML = data.documents.length
      ? data.documents
          .map(
            (document) => `
              <div class="document-row">
                <div>
                  <strong>${escapeHtml(document.file_name)}</strong>
                  <div class="muted">${escapeHtml(document.id)}</div>
                </div>
                <span class="status-pill ${escapeHtml(document.status)}">${escapeHtml(document.status)}</span>
                <span>${document.chunk_count ?? 0} chunks</span>
                <span class="muted">${formatTime(document.updated_at)}</span>
              </div>
            `,
          )
          .join("")
      : '<div class="muted">当前知识库暂无文档</div>';
  } catch (error) {
    showToast(`文档列表加载失败：${error.message}`);
  }
}

async function loadTasks() {
  try {
    const data = await request("/api/knowledge/tasks?limit=20");
    $("#taskList").innerHTML = data.tasks.length
      ? data.tasks
          .map(
            (task) => `
              <div class="compact-item">
                <strong>${escapeHtml(task.task_type)}</strong>
                <div><span class="status-pill ${escapeHtml(task.status)}">${escapeHtml(task.status)}</span> ${task.progress}%</div>
                <div class="muted">${escapeHtml(task.message || task.task_id)}</div>
                <div class="muted">${formatTime(task.updated_at)}</div>
              </div>
            `,
          )
          .join("")
      : '<div class="muted">暂无入库任务</div>';
  } catch (error) {
    showToast(`任务列表加载失败：${error.message}`);
  }
}

async function searchKnowledge(event) {
  event.preventDefault();
  const query = $("#knowledgeQuery").value.trim();

  if (!query) return;

  $("#knowledgeSearchResult").innerHTML = '<div class="muted">检索中...</div>';

  try {
    const data = await request("/api/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    $("#knowledgeSearchResult").innerHTML = `
      <div class="search-answer">${escapeHtml(data.answer)}</div>
      ${data.citations.length ? `<div class="muted">引用：${data.citations.map((item) => escapeHtml(item.source || item.chunk_id || "未知来源")).join("，")}</div>` : ""}
      ${data.retrieved_chunks
        .map(
          (chunk) => `
            <div class="search-chunk">
              <div class="muted">${escapeHtml(chunk.metadata?.source || "chunk")}</div>
              ${escapeHtml(chunk.content)}
            </div>
          `,
        )
        .join("")}
    `;
  } catch (error) {
    showToast(`知识库检索失败：${error.message}`);
  }
}

function getKnowledgeBaseId() {
  return $("#knowledgeBaseId")?.value.trim() || "default";
}
function labelFor(key) {
  return {
    conversations: "Conversations",
    messages: "Messages",
    knowledge_bases: "Knowledge Bases",
    documents: "Documents",
    chunks: "Chunks",
    knowledge_tasks: "Tasks",
    tool_calls: "Tool Calls",
  }[key] || key;
}

function formatTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

$("#chatForm").addEventListener("submit", sendMessage);
$("#newConversation").addEventListener("click", () => {
  state.conversationId = null;
  state.messages = [];
  renderMessages();
});
$("#refreshKnowledge").addEventListener("click", loadKnowledge);
$("#createBaseForm").addEventListener("submit", createKnowledgeBase);
$("#uploadForm").addEventListener("submit", uploadKnowledgeFile);
$("#knowledgeSearchForm").addEventListener("submit", searchKnowledge);
$("#refreshConversations").addEventListener("click", loadConversations);
$("#refreshMonitor").addEventListener("click", loadMonitor);
$("#refreshLogs").addEventListener("click", loadLogs);

renderMessages();

