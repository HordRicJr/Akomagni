const fs = require("fs");
const os = require("os");
const path = require("path");
const vscode = require("vscode");

const RODIUM_DEFAULT = "https://api.rodiumai.io/v1";
const LOCAL_DEFAULT = "http://127.0.0.1:8787/v1";

function akomagniConfigPath() {
  const base =
    process.platform === "win32"
      ? path.join(process.env.LOCALAPPDATA || os.homedir(), "akomagni")
      : path.join(os.homedir(), ".local", "share", "akomagni");
  return path.join(base, "config.yaml");
}

/** Minimal YAML reader for Akomagni config keys we need. */
function parseSimpleYaml(text) {
  const out = { inference: { provider: "local" }, providers: {} };
  let section = "";
  let sub = "";
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (!line || line.startsWith("#")) continue;
    if (!line.startsWith(" ") && line.endsWith(":")) {
      section = line.slice(0, -1);
      sub = "";
      if (!out[section]) out[section] = {};
      continue;
    }
    const m = line.match(/^(\s{2})(\w+):\s*(.*)$/);
    if (!m) continue;
    const key = m[2];
    let val = m[3].trim();
    if (val === "null" || val === "~") val = null;
    else if (val === "true") val = true;
    else if (val === "false") val = false;
    else if (/^\d+$/.test(val)) val = Number(val);
    else val = val.replace(/^['"]|['"]$/g, "");

    if (m[1] === "  " && section && !line.startsWith("    ")) {
      out[section][key] = val;
    }
    const m2 = line.match(/^ {4}(\w+):\s*(.*)$/);
    if (m2 && section === "providers") {
      if (!sub) continue;
      if (!out.providers[sub]) out.providers[sub] = {};
      let v2 = m2[2].trim().replace(/^['"]|['"]$/g, "");
      out.providers[sub][m2[1]] = v2;
    }
    const m3 = line.match(/^ {2}(\w+):\s*$/);
    if (m3 && section === "providers") sub = m3[1];
  }
  return out;
}

function loadFileConfig() {
  const cfgPath = akomagniConfigPath();
  if (!fs.existsSync(cfgPath)) return null;
  try {
    return parseSimpleYaml(fs.readFileSync(cfgPath, "utf8"));
  } catch {
    return null;
  }
}

function resolveEndpoint() {
  const ws = vscode.workspace.getConfiguration("akomagni");
  const fileCfg = loadFileConfig() || {};
  const provider = String(ws.get("provider") || fileCfg.inference?.provider || "local");
  const provBlock = (fileCfg.providers || {})[provider] || {};

  let baseUrl = String(ws.get("baseUrl") || provBlock.base_url || "").replace(/\/$/, "");
  let apiKey = String(ws.get("apiKey") || provBlock.api_key || "");
  let model = String(ws.get("model") || "");

  if (provider === "rodium") {
    baseUrl = baseUrl || RODIUM_DEFAULT;
    if (!model) model = provBlock.models?.code || "openai/gpt-4o";
  } else if (provider === "azure") {
    if (!model) model = provBlock.deployments?.code || provBlock.default_model || "gpt-4o";
  } else {
    baseUrl = baseUrl || LOCAL_DEFAULT;
    apiKey = "";
    if (!model) model = fileCfg.inference?.default_model || "local";
  }

  if (!apiKey && provider === "rodium") {
    apiKey = process.env.RODIUMAI_API_KEY || "";
  }
  if (!apiKey && provider === "azure") {
    apiKey = process.env.AZURE_OPENAI_API_KEY || "";
  }

  return {
    provider,
    baseUrl,
    apiKey,
    model,
    isLocal: provider === "local",
    bmadEnabled: ws.get("bmadRouting", true),
  };
}

module.exports = { resolveEndpoint, loadFileConfig, akomagniConfigPath };
