const vscode = require("vscode");
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

    try {
      webviewView.webview.html = this.getHtml(webviewView.webview);
    } catch (err) {
      console.error("[Akomagni] chat view failed to load:", err);
      webviewView.webview.html = this.getFallbackHtml(
        "Le panneau chat n'a pas pu démarrer. Réinstallez l'extension ou relancez VS Code.",
        String(err.message || err)
      );
      return;
    }

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      try {
        if (msg.type === "ready") this.sendStatus();
        if (msg.type === "send") await this.handleSend(String(msg.text || ""));
        if (msg.type === "newChat") this.resetChat();
        if (msg.type === "setProvider") await this.setProvider(String(msg.provider));
        if (msg.type === "setModel") await this.setModel(String(msg.model));
        if (msg.type === "refresh") this.sendStatus();
      } catch (err) {
        console.error("[Akomagni] message handler error:", err);
        this.post({ type: "error", text: String(err.message || err) });
      }
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
    try {
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
        ready: true,
      });
    } catch (err) {
      this.post({
        type: "status",
        provider: "local",
        model: "",
        baseUrl: "",
        online: false,
        models: [],
        hasKey: false,
        ready: true,
        initError: String(err.message || err),
      });
    }
  }

  async handleSend(text) {
    if (!text.trim()) return;
    const endpoint = resolveEndpoint();
    const folder = vscode.workspace.workspaceFolders?.[0];
    const wsName = folder?.name || "workspace";

    if (!endpoint.isLocal && !endpoint.apiKey) {
      this.post({
        type: "error",
        text: "Pas de clé API. Terminal : akomagni connect rodium  (ou : akomagni connect foundry <url>)",
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
        ? "Démarrez le serveur local : akomagni serve --model <nom>"
        : "Vérifiez la clé API et l'URL (akomagni inference status)";
      this.post({ type: "error", text: `Inférence hors ligne. ${hint}` });
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

  mediaUri(webview, ...parts) {
    return webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, ...parts));
  }

  getFallbackHtml(title, detail) {
    const safeTitle = title.replace(/</g, "&lt;");
    const safeDetail = detail.replace(/</g, "&lt;");
    return `<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8" /></head>
<body style="font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; line-height: 1.5;">
  <p><strong>${safeTitle}</strong></p>
  <p style="opacity:0.8;font-size:12px;">${safeDetail}</p>
  <p style="font-size:12px;">Installation CLI : <code>akomagni connect rodium</code> ou <code>akomagni serve</code></p>
</body>
</html>`;
  }

  getHtml(webview) {
    const style = this.mediaUri(webview, "media", "chat.css");
    const script = this.mediaUri(webview, "media", "chat.js");
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
  <div id="log">
    <div class="msg loading">Chargement d'Akomagni Chat…</div>
  </div>
  <div id="bar">
    <textarea id="input" rows="2" placeholder="Demandez à Akomagni (agents BMAD + inférence)…"></textarea>
    <button id="send">Envoyer</button>
  </div>
  <script nonce="${nonce}" src="${script}"></script>
</body>
</html>`;
  }
}

async function openChatPanel() {
  try {
    await vscode.commands.executeCommand("workbench.action.focusAuxiliaryBar");
  } catch {
    /* VS Code &lt; 1.97 */
  }
  try {
    await vscode.commands.executeCommand("workbench.view.extension.akomagni");
  } catch {
    await vscode.commands.executeCommand("akomagni.chatView.focus");
  }
}

function activate(context) {
  const provider = new AkomagniChatProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("akomagni.chatView", provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    vscode.commands.registerCommand("akomagni.openChat", () => openChatPanel()),
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
