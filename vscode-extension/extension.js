const vscode = require("vscode");
const https = require("https");
const http = require("http");

/** @type {vscode.WebviewView | undefined} */
let chatView;

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const provider = new AkomagniChatProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("akomagni.chatView", provider),
    vscode.commands.registerCommand("akomagni.openChat", () => {
      vscode.commands.executeCommand("akomagni.chatView.focus");
    }),
    vscode.commands.registerCommand("akomagni.newChat", () => {
      provider.resetChat();
    })
  );
}

function deactivate() {}

class AkomagniChatProvider {
  /** @param {vscode.Uri} extensionUri */
  constructor(extensionUri) {
    this.extensionUri = extensionUri;
    /** @type {vscode.WebviewView | undefined} */
    this.view = undefined;
    /** @type {Array<{role: string, content: string}>} */
    this.messages = [];
  }

  resetChat() {
    this.messages = [];
    if (this.view) {
      this.view.webview.postMessage({ type: "reset" });
    }
  }

  /** @param {vscode.WebviewView} webviewView */
  resolveWebviewView(webviewView) {
    this.view = webviewView;
    chatView = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };
    webviewView.webview.html = this.getHtml();
    webviewView.webview.onDidReceiveMessage(async (message) => {
      if (message.type === "send") {
        await this.handleUserMessage(String(message.text || ""));
      }
    });
  }

  /** @param {string} text */
  async handleUserMessage(text) {
    if (!text.trim()) return;
    this.messages.push({ role: "user", content: text });
    this.post({ type: "user", text });

    const config = vscode.workspace.getConfiguration("akomagni");
    const baseUrl = String(config.get("baseUrl") || "https://api.rodiumai.io/v1").replace(/\/$/, "");
    const apiKey = String(config.get("apiKey") || "");
    const model = String(config.get("model") || "openai/gpt-4o");

    if (!apiKey) {
      this.post({
        type: "error",
        text: "No API key. Run: akomagni connect rodium (or foundry <url>)",
      });
      return;
    }

    this.post({ type: "thinking" });
    try {
      const reply = await chatCompletion({
        baseUrl,
        apiKey,
        model,
        messages: this.messages,
      });
      this.messages.push({ role: "assistant", content: reply });
      this.post({ type: "assistant", text: reply });
    } catch (err) {
      this.post({ type: "error", text: String(err.message || err) });
    }
  }

  /** @param {object} payload */
  post(payload) {
    this.view?.webview.postMessage(payload);
  }

  getHtml() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />
  <style>
    body { font-family: var(--vscode-font-family); margin: 0; display: flex; flex-direction: column; height: 100vh; background: var(--vscode-editor-background); color: var(--vscode-editor-foreground); }
    #log { flex: 1; overflow-y: auto; padding: 12px; }
    .msg { margin-bottom: 10px; white-space: pre-wrap; line-height: 1.4; }
    .user { color: var(--vscode-textLink-foreground); }
    .assistant { color: var(--vscode-foreground); }
    .error { color: var(--vscode-errorForeground); }
    .thinking { opacity: 0.6; font-style: italic; }
    #bar { display: flex; gap: 8px; padding: 10px; border-top: 1px solid var(--vscode-panel-border); }
    #input { flex: 1; resize: none; min-height: 36px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; padding: 8px; }
    button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; padding: 8px 12px; cursor: pointer; }
  </style>
</head>
<body>
  <div id="log"><div class="msg thinking">Akomagni Chat — ask anything. Configure with <code>akomagni connect</code>.</div></div>
  <div id="bar">
    <textarea id="input" placeholder="Message Akomagni…"></textarea>
    <button id="send">Send</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const log = document.getElementById('log');
    const input = document.getElementById('input');
    document.getElementById('send').onclick = send;
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    function send() {
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      vscode.postMessage({ type: 'send', text });
    }
    window.addEventListener('message', (event) => {
      const m = event.data;
      if (m.type === 'reset') { log.innerHTML = ''; return; }
      if (m.type === 'thinking') {
        const el = document.createElement('div');
        el.className = 'msg thinking';
        el.id = 'thinking';
        el.textContent = 'Thinking…';
        log.appendChild(el);
        log.scrollTop = log.scrollHeight;
        return;
      }
      const thinking = document.getElementById('thinking');
      if (thinking) thinking.remove();
      const el = document.createElement('div');
      el.className = 'msg ' + (m.type || 'assistant');
      el.textContent = (m.type === 'user' ? '› ' : '') + m.text;
      log.appendChild(el);
      log.scrollTop = log.scrollHeight;
    });
  </script>
</body>
</html>`;
  }
}

/**
 * @param {{baseUrl: string, apiKey: string, model: string, messages: Array<{role: string, content: string}>}} opts
 * @returns {Promise<string>}
 */
function chatCompletion(opts) {
  const url = new URL(`${opts.baseUrl}/chat/completions`);
  const body = JSON.stringify({
    model: opts.model,
    messages: opts.messages,
    stream: false,
  });
  const lib = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = lib.request(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${opts.apiKey}`,
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${data}`));
            return;
          }
          try {
            const parsed = JSON.parse(data);
            resolve(parsed.choices[0].message.content);
          } catch (err) {
            reject(err);
          }
        });
      }
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

module.exports = { activate, deactivate };
