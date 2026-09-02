const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { resolveEndpoint } = require("./lib/config");
const { checkHealth, chatCompletion } = require("./lib/inference");
const { routeMessage, buildSystemPrompt } = require("./lib/bmad");

class AkomagniChatProvider {
  constructor(extensionUri) {
    this.extensionUri = extensionUri;
    this.view = undefined;
    this.messages = [];
    this.systemPrompt = "";
    this.lastRoute = null;
  }

  resetChat() {
    this.messages = [];
    this.systemPrompt = "";
    this.lastRoute = null;
    this.post({ type: "reset" });
    this.sendStatus();
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);
    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "ready") this.sendStatus();
      if (msg.type === "send") await this.handleSend(String(msg.text || ""));
      if (msg.type === "newChat") this.resetChat();
      if (msg.type === "setProvider") await this.setProvider(String(msg.provider));
      if (msg.type === "setModel") await this.setModel(String(msg.model));
      if (msg.type === "refresh") this.sendStatus();
    });
  }

  async setProvider(provider) {
    const cfg = vscode.workspace.getConfiguration("akomagni");
    await cfg.update("provider", provider, vscode.ConfigurationTarget.Workspace);
    this.sendStatus();
  }

  async setModel(model) {
    const cfg = vscode.workspace.getConfiguration("akomagni");
    await cfg.update("model", model, vscode.ConfigurationTarget.Workspace);
    this.sendStatus();
  }

  post(payload) {
    this.view?.webview.postMessage(payload);
  }

  async sendStatus() {
    const endpoint = resolveEndpoint();
    const health = await checkHealth(endpoint);
    this.post({
      type: "status",
      provider: endpoint.provider,
      model: endpoint.model,
      baseUrl: endpoint.baseUrl,
      online: health.online,
      models: health.models || [],
      hasKey: Boolean(endpoint.apiKey) || endpoint.isLocal,
    });
  }

  async handleSend(text) {
    if (!text.trim()) return;
    const endpoint = resolveEndpoint();
    const folder = vscode.workspace.workspaceFolders?.[0];
    const wsName = folder?.name || "workspace";

    if (!endpoint.isLocal && !endpoint.apiKey) {
      this.post({
        type: "error",
        text: "No API key. Run in terminal: akomagni connect rodium  (or: akomagni connect foundry <url>)",
      });
      return;
    }

    this.post({ type: "user", text });
    this.messages.push({ role: "user", content: text });

    let route = null;
    if (endpoint.bmadEnabled !== false) {
      route = await routeMessage(text, folder?.uri.fsPath);
      this.lastRoute = route;
      if (route) {
        this.post({
          type: "route",
          agent: route.agent_id,
          skill: route.skill,
          confidence: route.confidence,
          badge: route.badge,
        });
        this.systemPrompt = buildSystemPrompt(route, wsName);
      }
    }

    const health = await checkHealth(endpoint);
    if (!health.online) {
      const hint = endpoint.isLocal
        ? "Start local server: akomagni serve --model <name>"
        : "Check API key and URL (akomagni inference status)";
      this.post({ type: "error", text: `Inference offline. ${hint}` });
      return;
    }

    this.post({ type: "thinking" });
    try {
      const reply = await chatCompletion(endpoint, this.messages, this.systemPrompt);
      this.messages.push({ role: "assistant", content: reply });
      this.post({ type: "assistant", text: reply });
    } catch (err) {
      this.post({ type: "error", text: String(err.message || err) });
    }
  }

  getHtml(webview) {
    const style = webview.asWebviewUri(path.join(this.extensionUri, "media", "chat.css"));
    const script = webview.asWebviewUri(path.join(this.extensionUri, "media", "chat.js"));
    const nonce = String(Date.now());
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';" />
  <link rel="stylesheet" href="${style}" />
</head>
<body>
  <header id="toolbar">
    <select id="provider" title="Provider">
      <option value="local">Local</option>
      <option value="rodium">Rodium AI</option>
      <option value="azure">Azure Foundry</option>
    </select>
    <select id="model" title="Model"></select>
    <span id="status-dot" title="Status"></span>
    <button id="newChat" title="New chat">+</button>
  </header>
  <div id="log"></div>
  <div id="bar">
    <textarea id="input" rows="2" placeholder="Ask Akomagni (BMAD agents + inference)…"></textarea>
    <button id="send">Send</button>
  </div>
  <script nonce="${nonce}" src="${script}"></script>
</body>
</html>`;
  }
}

function activate(context) {
  const provider = new AkomagniChatProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("akomagni.chatView", provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    vscode.commands.registerCommand("akomagni.openChat", () => {
      vscode.commands.executeCommand("akomagni.chatView.focus");
    }),
    vscode.commands.registerCommand("akomagni.newChat", () => provider.resetChat()),
    vscode.commands.registerCommand("akomagni.connectRodium", async () => {
      const term = vscode.window.createTerminal("Akomagni Connect");
      term.show();
      term.sendText("akomagni connect rodium");
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
