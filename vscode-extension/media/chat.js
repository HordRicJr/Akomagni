(function () {
  const vscode = acquireVsCodeApi();
  const log = document.getElementById("log");
  const input = document.getElementById("input");
  const providerSel = document.getElementById("provider");
  const modelSel = document.getElementById("model");
  const statusDot = document.getElementById("status-dot");

  log.innerHTML =
    '<div class="msg welcome">Akomagni Chat — BMAD agents + local / Rodium / Azure Foundry.<br>Run <code>akomagni connect rodium</code> or start <code>akomagni serve</code> for local models.</div>';

  document.getElementById("send").onclick = send;
  document.getElementById("newChat").onclick = () => vscode.postMessage({ type: "newChat" });
  providerSel.onchange = () => vscode.postMessage({ type: "setProvider", provider: providerSel.value });
  modelSel.onchange = () => vscode.postMessage({ type: "setModel", model: modelSel.value });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  function send() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    vscode.postMessage({ type: "send", text });
  }

  function append(type, text, extra) {
    const el = document.createElement("div");
    el.className = "msg " + type;
    if (type === "route" && extra) {
      el.textContent = `${extra.badge || ""} agent=${extra.agent} · skill=${extra.skill} (${Math.round((extra.confidence || 0) * 100)}%)`;
    } else if (type === "user") {
      el.textContent = "› " + text;
    } else {
      el.textContent = text;
    }
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  window.addEventListener("message", (event) => {
    const m = event.data;
    if (m.type === "reset") {
      log.innerHTML =
        '<div class="msg welcome">New chat. BMAD routing + inference ready.</div>';
      return;
    }
    if (m.type === "status") {
      providerSel.value = m.provider || "local";
      statusDot.className = "online";
      statusDot.classList.toggle("online", m.online);
      statusDot.classList.toggle("offline", !m.online);
      statusDot.title = m.online ? "Online: " + m.baseUrl : "Offline";
      const models = m.models && m.models.length ? m.models : [m.model];
      modelSel.innerHTML = "";
      models.forEach((id) => {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = id;
        if (id === m.model) opt.selected = true;
        modelSel.appendChild(opt);
      });
      if (!modelSel.value && m.model) {
        const opt = document.createElement("option");
        opt.value = m.model;
        opt.textContent = m.model;
        opt.selected = true;
        modelSel.appendChild(opt);
      }
      return;
    }
    if (m.type === "thinking") {
      const el = append("thinking", "Thinking…");
      el.id = "thinking";
      return;
    }
    const thinking = document.getElementById("thinking");
    if (thinking) thinking.remove();
    if (m.type === "route") append("route", "", m);
    else if (m.type === "user" || m.type === "assistant" || m.type === "error") append(m.type, m.text);
  });

  vscode.postMessage({ type: "ready" });
})();
