const groceryListEl = document.getElementById("groceryList");
const todoListEl = document.getElementById("todoList");
const statusEl = document.getElementById("status");
const asrStatusEl = document.getElementById("asrStatus");
const ollamaStatusEl = document.getElementById("ollamaStatus");
const logEl = document.getElementById("log");
const addForm = document.getElementById("addForm");
const itemText = document.getElementById("itemText");
const listType = document.getElementById("listType");
const priority = document.getElementById("priority");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const clearTranscriptBtn = document.getElementById("clearTranscriptBtn");
const pendingListEl = document.getElementById("pendingList");
const clearPendingBtn = document.getElementById("clearPendingBtn");
const bulkPendingListTypeEl = document.getElementById("bulkPendingListType");
const confirmAllPendingBtn = document.getElementById("confirmAllPendingBtn");
const setupSection = document.getElementById("setupSection");
const setupStatus = document.getElementById("setupStatus");
const runSetupBtn = document.getElementById("runSetupBtn");
const grocerySort = document.getElementById("grocerySort");
const todoSort = document.getElementById("todoSort");

function row(item) {
  const li = document.createElement("li");
  li.className = item.completed ? "done" : "";
  li.dataset.priority = item.priority || 1;

  const left = document.createElement("div");
  left.style.display = "flex";
  left.style.alignItems = "center";
  left.style.gap = "8px";
  left.style.flex = "1";

  // Priority indicator
  const priorityBadge = document.createElement("span");
  priorityBadge.className = "priority-badge";
  priorityBadge.textContent = getPriorityLabel(item.priority || 1);
  priorityBadge.dataset.priority = item.priority || 1;
  left.appendChild(priorityBadge);

  const label = document.createElement("span");
  label.textContent = item.text;
  label.title = `From: ${item.source_text}`;
  left.appendChild(label);

  li.appendChild(left);

  const actions = document.createElement("div");
  actions.style.display = "flex";
  actions.style.gap = "8px";
  actions.style.alignItems = "center";

  // Priority selector
  const prioritySelect = document.createElement("select");
  prioritySelect.className = "priority-select";
  [1, 2, 3].forEach((p) => {
    const option = document.createElement("option");
    option.value = p;
    option.textContent = getPriorityLabel(p);
    if (p === (item.priority || 1)) {
      option.selected = true;
    }
    prioritySelect.appendChild(option);
  });
  prioritySelect.onchange = async () => {
    await fetch(`/api/list-items/${item.id}/priority`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ priority: parseInt(prioritySelect.value) }),
    });
    await loadState();
  };
  actions.appendChild(prioritySelect);

  const toggleBtn = document.createElement("button");
  toggleBtn.textContent = item.completed ? "Undo" : "Done";
  toggleBtn.onclick = async () => {
    await fetch(`/api/list-items/${item.id}/toggle`, { method: "POST" });
    await loadState();
  };
  actions.appendChild(toggleBtn);

  const delBtn = document.createElement("button");
  delBtn.textContent = "Delete";
  delBtn.onclick = async () => {
    await fetch(`/api/list-items/${item.id}`, { method: "DELETE" });
    await loadState();
  };
  actions.appendChild(delBtn);

  li.appendChild(actions);
  return li;
}

function getPriorityLabel(priority) {
  switch (priority) {
    case 3:
      return "High";
    case 2:
      return "Med";
    case 1:
    default:
      return "Low";
  }
}

function pendingRow(item) {
  const li = document.createElement("li");

  const left = document.createElement("div");
  left.innerHTML = `<strong>${item.text}</strong><br><small>confidence: ${item.confidence} | suggested: ${item.suggested_list_type}</small>`;
  li.appendChild(left);

  const actions = document.createElement("div");

  const select = document.createElement("select");
  ["grocery", "todo"].forEach((type) => {
    const option = document.createElement("option");
    option.value = type;
    option.textContent = type;
    if (type === item.suggested_list_type) {
      option.selected = true;
    }
    select.appendChild(option);
  });
  actions.appendChild(select);

  const confirmBtn = document.createElement("button");
  confirmBtn.textContent = "Confirm";
  confirmBtn.onclick = async () => {
    await fetch(`/api/pending/${item.id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ list_type: select.value, priority: 1 }),
    });
    await loadState();
  };
  actions.appendChild(confirmBtn);

  const removeBtn = document.createElement("button");
  removeBtn.textContent = "Remove";
  removeBtn.onclick = async () => {
    await fetch(`/api/pending/${item.id}`, { method: "DELETE" });
    await loadState();
  };
  actions.appendChild(removeBtn);

  li.appendChild(actions);
  return li;
}

async function loadState() {
  const res = await fetch("/api/lists");
  const state = await res.json();
  statusEl.textContent = `Listening: ${state.listening}`;
  
  // Update status classes for visual feedback
  statusEl.className = state.listening ? "listening" : "not-listening";
  
  const modelLabel = state.asr_model ? ` (${state.asr_model})` : "";
  asrStatusEl.textContent = `ASR: ${state.asr_status}${modelLabel}`;
  
  // Update ASR status class
  asrStatusEl.className = "";
  if (state.asr_status === "ready") {
    asrStatusEl.classList.add("ready");
  } else if (state.asr_status === "loading") {
    asrStatusEl.classList.add("loading");
  }
  
  const ollamaModelLabel = state.ollama_model ? ` (${state.ollama_model})` : "";
  ollamaStatusEl.textContent = `Ollama: ${state.ollama_status}${ollamaModelLabel}`;
  
  // Update Ollama status class
  ollamaStatusEl.className = "";
  if (state.ollama_status === "connected") {
    ollamaStatusEl.classList.add("ready");
  } else if (state.ollama_status === "disconnected") {
    ollamaStatusEl.classList.add("not-listening");
  }
  
  startBtn.disabled = state.asr_status === "loading" || state.asr_status === "missing_model";
  if (state.asr_status === "missing_model") {
    asrStatusEl.textContent = "ASR: missing model";
  }

  groceryListEl.innerHTML = "";
  todoListEl.innerHTML = "";
  pendingListEl.innerHTML = "";
  state.grocery.forEach((i) => groceryListEl.appendChild(row(i)));
  state.todo.forEach((i) => todoListEl.appendChild(row(i)));
  state.pending_review.forEach((i) => pendingListEl.appendChild(pendingRow(i)));
  logEl.textContent = state.transcript_log.join("\n");

  // Check setup status
  await checkSetupStatus();
}

async function checkSetupStatus() {
  try {
    const res = await fetch("/api/setup/status");
    const setup = await res.json();
    
    if (!setup.vosk_available || !setup.ollama_connected) {
      setupSection.style.display = "block";
      let statusHtml = "<ul>";
      statusHtml += `<li>Vosk Model: ${setup.vosk_available ? "✓ Available" : "✗ Not found"}</li>`;
      statusHtml += `<li>Ollama: ${setup.ollama_connected ? "✓ Connected" : "✗ Not connected"}</li>`;
      statusHtml += "</ul>";
      
      if (!setup.vosk_available) {
        statusHtml += "<p><strong>Vosk Model Required:</strong> Download from <a href='https://alphacephei.com/vosk/models' target='_blank'>alphacephei.com</a> and extract to app directory.</p>";
      }
      if (!setup.ollama_connected) {
        statusHtml += "<p><strong>Ollama Required:</strong> Install from <a href='https://ollama.com/download' target='_blank'>ollama.com</a>. After installation, pull the model: <code>ollama pull llama3.1:8b</code></p>";
      }
      
      setupStatus.innerHTML = statusHtml;
    } else {
      setupSection.style.display = "none";
    }
  } catch (e) {
    console.error("Failed to check setup status:", e);
  }
}

addForm.onsubmit = async (e) => {
  e.preventDefault();
  const body = {
    text: itemText.value.trim(),
    list_type: listType.value,
    priority: parseInt(priority.value),
  };
  if (!body.text) {
    return;
  }
  await fetch("/api/list-items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  itemText.value = "";
  await loadState();
};

startBtn.onclick = async () => {
  const res = await fetch("/api/listening/start", { method: "POST" });
  if (!res.ok) {
    const payload = await res.json();
    alert(payload.detail || "Failed to start listening");
  }
  await loadState();
};

stopBtn.onclick = async () => {
  await fetch("/api/listening/stop", { method: "POST" });
  await loadState();
};

clearTranscriptBtn.onclick = async () => {
  await fetch("/api/transcript/clear", { method: "POST" });
  await loadState();
};

clearPendingBtn.onclick = async () => {
  await fetch("/api/pending/clear", { method: "POST" });
  await loadState();
};

confirmAllPendingBtn.onclick = async () => {
  await fetch("/api/pending/confirm-all", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ list_type: bulkPendingListTypeEl.value, priority: 1 }),
  });
  await loadState();
};

grocerySort.onchange = async () => {
  await fetch(`/api/lists/grocery/sort`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sort_by: grocerySort.value }),
  });
  await loadState();
};

todoSort.onchange = async () => {
  await fetch(`/api/lists/todo/sort`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sort_by: todoSort.value }),
  });
  await loadState();
};

runSetupBtn.onclick = async () => {
  const res = await fetch("/api/setup/run", { method: "POST" });
  const result = await res.json();
  if (result.status === "started") {
    runSetupBtn.textContent = "Setup Running...";
    runSetupBtn.disabled = true;
    setupStatus.innerHTML += "<p>Setup wizard is running in the background. This may take several minutes...</p>";
    // Check status periodically
    const checkInterval = setInterval(async () => {
      await checkSetupStatus();
      const setupRes = await fetch("/api/setup/status");
      const setup = await setupRes.json();
      if (setup.vosk_available && setup.ollama_connected) {
        clearInterval(checkInterval);
        runSetupBtn.textContent = "Setup Complete!";
        setTimeout(() => {
          runSetupBtn.textContent = "Run Setup Wizard";
          runSetupBtn.disabled = false;
        }, 3000);
      }
    }, 5000);
  } else {
    alert(result.message || "Setup wizard not available");
  }
};

loadState();
setInterval(loadState, 1500);
