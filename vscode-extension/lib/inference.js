const https = require("https");
const http = require("http");

function requestJson(url, { method = "GET", body = null, apiKey = null, timeout = 60000 }) {
  return new Promise((resolve, reject) => {
    const lib = url.protocol === "https:" ? https : http;
    const payload = body ? JSON.stringify(body) : null;
    const headers = { Accept: "application/json" };
    if (payload) {
      headers["Content-Type"] = "application/json";
      headers["Content-Length"] = Buffer.byteLength(payload);
    }
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;

    const req = lib.request(
      url,
      { method, headers, timeout },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          if (res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${data.slice(0, 400)}`));
            return;
          }
          try {
            resolve(data ? JSON.parse(data) : {});
          } catch (err) {
            reject(err);
          }
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => req.destroy(new Error("Request timeout")));
    if (payload) req.write(payload);
    req.end();
  });
}

async function checkHealth(endpoint) {
  try {
    const modelsUrl = new URL(`${endpoint.baseUrl}/models`);
    const data = await requestJson(modelsUrl, { apiKey: endpoint.apiKey || null, timeout: 8000 });
    const ids = (data.data || []).map((m) => m.id).filter(Boolean);
    return { online: true, models: ids };
  } catch (err) {
    if (endpoint.isLocal) {
      try {
        const health = new URL(endpoint.baseUrl.replace(/\/v1$/, "") + "/health");
        await requestJson(health, { timeout: 3000 });
        return { online: true, models: [] };
      } catch {
        /* fall through */
      }
    }
    return { online: false, error: String(err.message || err) };
  }
}

async function chatCompletion(endpoint, messages, systemPrompt) {
  const msgs = [];
  if (systemPrompt) msgs.push({ role: "system", content: systemPrompt });
  msgs.push(...messages);
  const url = new URL(`${endpoint.baseUrl}/chat/completions`);
  const data = await requestJson(url, {
    method: "POST",
    apiKey: endpoint.apiKey || null,
    body: { model: endpoint.model, messages: msgs, stream: false },
    timeout: 120000,
  });
  return data.choices[0].message.content;
}

module.exports = { checkHealth, chatCompletion };
