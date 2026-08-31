# Create GitHub labels and issues for Akomagni roadmap
# Requires: gh CLI authenticated

$labels = @(
    @{ name = "epic"; color = "7057ff"; desc = "Large feature umbrella" },
    @{ name = "priority:high"; color = "b60205"; desc = "High priority" },
    @{ name = "priority:medium"; color = "fbca04"; desc = "Medium priority" },
    @{ name = "priority:low"; color = "0e8a16"; desc = "Low priority" },
    @{ name = "area:inference"; color = "1d76db"; desc = "Local inference / models" },
    @{ name = "area:flow"; color = "5319e7"; desc = "Akomagni Flow orchestration" },
    @{ name = "area:memory"; color = "f9d0c4"; desc = "Akomagni Memory" },
    @{ name = "area:rag"; color = "c2e0c6"; desc = "RAG ingestion and retrieval" },
    @{ name = "area:ide"; color = "bfdadc"; desc = "Akomagni IDE fork" },
    @{ name = "area:ci"; color = "ededed"; desc = "CI/CD and quality" },
    @{ name = "area:docs"; color = "0075ca"; desc = "Documentation" },
    @{ name = "area:security"; color = "d93f0b"; desc = "Security" },
    @{ name = "good first issue"; color = "7057ff"; desc = "Good for newcomers" }
)

foreach ($l in $labels) {
    gh label create $l.name --color $l.color --description $l.desc 2>$null
}

$issues = @(
    @{ title = "[EPIC] v0.2 - Local inference (llama.cpp + model pull)"; labels = "epic,area:inference,priority:high"; body = "Goal: Integrate local GGUF inference via llama.cpp with HuggingFace model downloads.`n`nSub-tasks:`n- llama-server subprocess wrapper`n- akomagni model pull`n- OpenAI-compatible API on :8787`n- Wire akomagni run cli to inference backend" },
    @{ title = "Integrate llama-server subprocess for akomagni serve"; labels = "area:inference,priority:high"; body = "Wrap llama.cpp llama-server as subprocess. Bind 127.0.0.1:8787. Health check. Cross-platform Win/Linux." },
    @{ title = "Implement akomagni model pull (HuggingFace GGUF)"; labels = "area:inference,priority:high"; body = "Download GGUF models to ~/.akomagni/models/. Progress bar. Resume support." },
    @{ title = "OpenAI-compatible chat API on port 8787"; labels = "area:inference,priority:high"; body = "Expose /v1/chat/completions. Document usage with OpenAI client libraries." },
    @{ title = "Wire CLI chat to local inference backend"; labels = "area:inference,area:flow,priority:high"; body = "akomagni run cli calls local API after Flow routes. Fallback when server offline." },
    @{ title = "[EPIC] v0.2 - Akomagni Flow production"; labels = "epic,area:flow,priority:high"; body = "Production orchestration: gates, subprocess skill invoke, state machine." },
    @{ title = "Parse bmad-help.csv for workflow gates"; labels = "area:flow,priority:high"; body = "Load catalog at startup. Enforce preceded-by and required gates." },
    @{ title = "BMAD skill subprocess invocation (uv run)"; labels = "area:flow,priority:high"; body = "Invoke skills via uv run. Pass memory context and user message." },
    @{ title = "Domain model router - swap models per task"; labels = "area:flow,area:inference,priority:medium"; body = "Classify code/design/image/text. Hot-swap GGUF workers." },
    @{ title = "[EPIC] v0.2 - Akomagni Memory"; labels = "epic,area:memory,priority:medium"; body = "memory add --global, memory promote, auto-capture with approval." },
    @{ title = "memory add and memory promote commands"; labels = "area:memory,priority:medium"; body = "CLI commands for global learnings and promote project to central." },
    @{ title = "[EPIC] v0.2 - RAG (ingest + retrieval)"; labels = "epic,area:rag,priority:medium"; body = "akomagni rag ingest/query. Hybrid BM25+vector. sqlite-vec." },
    @{ title = "Reach 90 percent unit test coverage"; labels = "area:ci,priority:high,good first issue"; body = "Current coverage about 49 percent. Add tests until CI --cov-fail-under=90 passes." },
    @{ title = "Production-ready install scripts (curl / irm)"; labels = "area:ci,priority:medium"; body = "Harden install.sh and install.ps1. PATH setup. Smoke test." },
    @{ title = "[EPIC] v0.3 - Akomagni Train (LoRA)"; labels = "epic,area:inference,priority:low"; body = "QLoRA/LoRA local fine-tuning from Akomagni Memory." },
    @{ title = "ML intent router (3B classification model)"; labels = "area:flow,priority:low"; body = "Replace heuristic intent.py with local 3B router. Target 85 percent accuracy." },
    @{ title = "[EPIC] v1.0 - Akomagni IDE (VS Code fork)"; labels = "epic,area:ide,priority:low"; body = "Fork Code-OSS. Chat sidebar. Build Win+Linux." },
    @{ title = "Site akomagni.dev - static documentation"; labels = "area:docs,priority:medium"; body = "Static site with /code /design /write /models /memory." },
    @{ title = "French CLI output (i18n)"; labels = "area:docs,priority:low"; body = "Localize CLI from config language preference." },
    @{ title = "Agent MCP tools with sandbox (fs, shell, git)"; labels = "area:security,priority:medium"; body = "MCP tools for agent mode. Approval before destructive ops." },
    @{ title = "Configure branch protection on develop and main"; labels = "area:ci,priority:high"; body = "Require PR reviews and status checks. No direct push to main." },
    @{ title = "CI/CD - quality, coverage, security, secrets"; labels = "area:ci,priority:high"; body = "Workflows: quality.yml, test.yml with 90 percent coverage gate, security.yml with pip-audit bandit gitleaks." }
)

foreach ($i in $issues) {
    gh issue create --title $i.title --label $i.labels --body $i.body
}

Write-Host "Created $($issues.Count) issues."
