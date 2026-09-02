const { execFile } = require("child_process");
const path = require("path");

function findAkomagniCommand() {
  const local = path.join(
    process.env.LOCALAPPDATA || "",
    "akomagni",
    ".venv",
    "Scripts",
    "akomagni.exe"
  );
  const userBin = path.join(process.env.USERPROFILE || "", ".local", "bin", "akomagni.exe");
  const fs = require("fs");
  if (fs.existsSync(local)) return local;
  if (fs.existsSync(userBin)) return userBin;
  return "akomagni";
}

function routeMessage(message, cwd) {
  return new Promise((resolve) => {
    const cmd = findAkomagniCommand();
    execFile(
      cmd,
      ["flow", "route", message, "--json"],
      { cwd: cwd || process.cwd(), timeout: 30000, env: { ...process.env, PYTHONUTF8: "1" } },
      (err, stdout) => {
        if (err || !stdout) {
          resolve(null);
          return;
        }
        try {
          resolve(JSON.parse(stdout.trim()));
        } catch {
          resolve(null);
        }
      }
    );
  });
}

function buildSystemPrompt(route, workspaceName) {
  if (!route) {
    return `You are Akomagni, a helpful AI assistant in VS Code (workspace: ${workspaceName}). Answer clearly in the user's language.`;
  }
  return [
    `You are the Akomagni BMAD agent \`${route.agent_id}\` using skill \`${route.skill}\`.`,
    `Routing confidence: ${Math.round((route.confidence || 0) * 100)}%.`,
    route.hint || "",
    `Workspace: ${workspaceName}.`,
    "Follow the skill workflow. Answer in the user's language.",
  ].join("\n");
}

module.exports = { routeMessage, buildSystemPrompt, findAkomagniCommand };
