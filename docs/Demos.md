# Golem — Demo Catalogue

A living catalogue of runnable demos. Each entry maps directly to a folder under
[`examples/`](https://github.com/sasadangelo/golem-runner/tree/main/examples) in the
`golem-runner` repository. Demos are listed in recommended presentation order.

---

## Feature Tags

| Tag | Meaning |
|---|---|
| `agents-md` | `AGENTS.md` persona injection |
| `skill-md` | `SKILL.md` procedural protocol injection |
| `bash` | embedded bash tool |
| `http_check` | embedded HTTP health-check tool |
| `mcp-k8s` | Kubernetes MCP server (live cluster queries) |
| `mcp-fs` | MCP filesystem server |
| `mcp-llmwiki` | LLM Wiki MCP server (RAG + wiki management) |
| `timer` | background timer/cron trigger |
| `slack` | Slack Incoming Webhook alert |
| `a2a` | Agent-to-Agent task delegation |

---

## Demo Index

| # | Name | Folder | Tags | Audience | Duration | Wow moment |
|---|---|---|---|---|---|---|
| 1 | [Bonnie — Chatbot](#1--bonnie--chatbot) | `demo-chatbot` | `agents-md` | any | 3 min | pure LLM conversation, zero tools |
| 2 | [Fabio — SRE Agent](#2--fabio--sre-agent) | `demo-sre` | `bash` `http_check` `mcp-k8s` `agents-md` `skill-md` | technical | 7 min | live Kubernetes cluster inspection |
| 3 | [Gianluca — Doc Agent](#3--gianluca--doc-agent) | `demo-doc` | `mcp-llmwiki` `agents-md` | technical / knowledge mgmt | 10 min | PDF → cited wiki in one chat |
| 4 | [Matteo — Monitor Agent](#4--matteo--monitor-agent) | `demo-monitor` | `http_check` `bash` `timer` `slack` `agents-md` | devops / business | 5 min | autonomous Slack alert, no human polling |
| 5 | [A2A Pipeline — Log Analyzer + Report Writer](#5--a2a-pipeline--log-analyzer--report-writer) | `demo-a2a` | `bash` `a2a` `agents-md` `skill-md` | technical / business | 8 min | one CLI command triggers a 2-agent pipeline |

---

## Demos

---

### 1 · Bonnie — Chatbot

**Persona:** Bonnie, a general-purpose conversational assistant.
No tools, no MCP servers, no skills — just the LLM behind an `AGENTS.md` persona.

**Folder:** `examples/demo-chatbot/` ✅ implemented

**The moment the audience remembers:**
> A single CLI command deploys a named, opinionated assistant. No code, no rebuild —
> just an `AGENTS.md` and a `config.yaml`. The platform is live in seconds.

**Deploy:**
```bash
examples/demo-chatbot/deploy.sh
golem agent status --id demo-chatbot-001   # → running
golem chat --id demo-chatbot-001
```

**Demo questions:**
```
Who are you and what can you do?
Explain the difference between a VM and a container.
Help me think through the pros and cons of a microservices architecture.
```

**Why it is impressive:**
- Establishes the baseline: this is what the platform looks like at its simplest
- Shows that identity and behaviour come from `AGENTS.md`, not from hard-coded prompts
- Zero external dependencies — works with no MCP servers, no tools, no secrets beyond WatsonX

**Requires:** `agents-md`

---

### 2 · Fabio — SRE Agent

**Persona:** Fabio, Senior Site Reliability Engineer.
Probes HTTP endpoints, inspects the container environment, queries the live Kubernetes
cluster via MCP, and produces structured incident reports.

**Folder:** `examples/demo-sre/` ✅ implemented

**The moment the audience remembers:**
> You ask "check the golem-control-plane namespace for issues" and Fabio calls three MCP
> tools autonomously — `list_pods`, `list_events`, `http_check` — then synthesises
> all results into a single incident report without being told how.

**Deploy:**
```bash
# 1 — deploy the Kubernetes MCP server (once per cluster)
examples/demo-sre/mcp/kubernetes/deploy.sh

# 2 — deploy Fabio
golem agent create \
  --config    examples/demo-sre/agent/config.yaml \
  --agents-md examples/demo-sre/agent/AGENTS.md \
  --skill     examples/demo-sre/agent/skills/check-health.md \
  --skill     examples/demo-sre/agent/skills/inspect-env.md \
  --skill     examples/demo-sre/agent/skills/inspect-k8s.md

golem agent status --id demo-sre-001   # → running
golem chat --id demo-sre-001
```

**Demo conversation:**
```
Who are you and what can you do?

Check if https://google.com is reachable and give me a structured report.

Give me a full environment report of this container: resources, mounted files,
running processes.

List all pods across all namespaces and tell me if anything is failing.

The golem-control-plane namespace might have issues. Check the pod statuses there,
look for any warning events, and also verify the control plane HTTP endpoint is reachable.

Give me a full cluster health report: namespaces, deployments, any failing workloads.
```

**Why it is impressive:**
- `AGENTS.md` tells Fabio *when* to use `bash` vs `http_check` vs MCP tools — no ambiguity
- `SKILL.md` files make every report structurally identical: Summary → Findings → Root Cause → Recommendations
- Cross-tool correlation (HTTP + K8s events + pod status) in a single response
- Real Kubernetes API data, not a simulation

**Teardown:**
```bash
golem agent delete --id demo-sre-001
# optional: helm uninstall -n kubernetes-mcp-server kubernetes-mcp-server
```

**Requires:** `bash` `http_check` `mcp-k8s` `agents-md` `skill-md`

---

### 3 · Gianluca — Doc Agent

**Persona:** Gianluca, Document Knowledge Assistant.
Ingests PDFs and notes via a web UI, builds a structured wiki through MCP tools,
and answers questions from the knowledge base with footnote citations.

**Folder:** `examples/demo-doc/` ✅ implemented

**Architecture:**
```
Browser  http://localhost:3000
    └──► llmwiki-web (Next.js)
              │ REST  http://localhost:8000
              ▼
    ┌─────────────────────────────────────┐
    │  Pod: llmwiki  (emptyDir /workspace)│
    │  container: api  :8000              │
    │  container: mcp  :8080              │
    │  /workspace/wiki/  ← Markdown pages │
    │  /workspace/*.pdf  ← raw sources    │
    └─────────────────────────────────────┘
              ▲  MCP  http://llmwiki-mcp:8080/mcp
    ┌─────────┴──────────┐
    │     Gianluca        │  demo-doc-001
    └─────────────────────┘
```

**The moment the audience remembers:**
> You upload a PDF in the browser. You ask Gianluca to read it. Thirty seconds later
> the wiki sidebar shows three new pages — concepts, entities, overview — with full
> Markdown rendering and footnote citations pointing to exact page numbers.

**Deploy:**
```bash
# 1 — build and deploy the llmwiki stack (once per cluster)
examples/demo-doc/mcp/llmwiki/deploy.sh
kubectl rollout status deployment/llmwiki
kubectl rollout status deployment/llmwiki-web

# 2 — deploy Gianluca
examples/demo-doc/deploy.sh
golem agent status --id demo-doc-001   # → running

# 3 — expose services
kubectl port-forward svc/llmwiki-mcp  8080:8080 &
kubectl port-forward svc/llmwiki-api  8000:8000 &
kubectl port-forward svc/llmwiki-web  3000:3000 &
```

**Demo steps:**
1. Open **http://localhost:3000** → **Sources → Upload** → drag `attention-is-all-you-need.pdf`
2. Open a chat: `golem chat --id demo-doc-001`

```
Hi Gianluca, what can you help me with?

I've uploaded attention-is-all-you-need.pdf — read it and create wiki pages.

What are the main contributions of the Transformer paper?

Is the wiki in good shape?
```

3. Refresh **http://localhost:3000** — wiki pages appear under the **Wiki** sidebar.

**Why it is impressive:**
- Raw PDF → cited, structured Markdown wiki with zero manual curation
- The audience can browse the result in the UI in real time
- Answers carry footnotes pointing to exact page numbers — not hallucinated knowledge
- `lint` detects hygiene issues (missing frontmatter, broken links) automatically

**Teardown:**
```bash
golem agent delete --id demo-doc-001
helm uninstall llmwiki llmwiki-web
```

**Requires:** `mcp-llmwiki` `agents-md`

---

### 4 · Matteo — Monitor Agent

**Persona:** Matteo, Site Reliability Agent.
Polls an HTTP endpoint on a 30-second timer, sends a Slack alert when the service
goes down, and sends a recovery notification when it comes back up.
No open chat session required — runs entirely in background.

**Folder:** `examples/demo-monitor/` ✅ implemented

```
[timer: every 30s]
      ↓
  http_check → mock-service /health
      ↓
  HTTP 200?  →  log "✅ healthy"
  HTTP 503?  →  bash curl → Slack "🚨 SERVICE DOWN"
               (next tick, if 200) → Slack "✅ SERVICE RECOVERED"
```

**The moment the audience remembers:**
> Nobody is watching. You flip the mock service to `DOWN` via a curl command.
> Thirty seconds later a Slack message arrives: *🚨 SERVICE DOWN*. You flip it
> back. Another message: *✅ SERVICE RECOVERED*. The agent never stops watching.

**Setup:**
```bash
# 1 — create your Slack Incoming Webhook
#     api.slack.com/apps → New App → Incoming Webhooks → Add to Workspace

# 2 — configure the secret
cd examples/demo-monitor && cp .env.example .env
# edit .env: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# 3 — deploy the mock service
examples/demo-monitor/mock-service/deploy.sh
kubectl port-forward -n demo-monitor svc/mock-service 8080:8080 &
curl http://localhost:8080/health
# → {"status": "ok", "service": "mock-service"}

# 4 — deploy Matteo (injects SLACK_WEBHOOK_URL as a K8s Secret automatically)
examples/demo-monitor/deploy.sh
golem agent tasks --agent demo-monitor-001   # tasks accumulate every 30s
```

**Live demo sequence:**
```bash
# bring the service DOWN
curl -X POST http://localhost:8080/admin/down
# → {"status": "DOWN"}
# wait ~30s → Slack: 🚨 SERVICE DOWN

# bring it back UP
curl -X POST http://localhost:8080/admin/up
# → {"status": "UP"}
# wait ~30s → Slack: ✅ SERVICE RECOVERED
```

**Why it is impressive:**
- The agent keeps running on its own schedule — no human intervention
- Alert format is consistent every time (`AGENTS.md` defines the exact template)
- Secrets (Slack webhook) are injected as Kubernetes Secrets, never baked into images
- `golem agent tasks` provides full observability of every autonomous check cycle

**Teardown:**
```bash
kubectl delete namespace demo-monitor-001
kubectl delete namespace demo-monitor
```

**Requires:** `http_check` `bash` `timer` `slack` `agents-md`

---

### 5 · A2A Pipeline — Log Analyzer + Report Writer

**Personas:**
- **Log Analyzer** — fetches live application logs, computes error rates, produces structured findings, delegates to the Report Writer.
- **Report Writer** — receives findings via A2A delegation and produces a polished Markdown incident report.

**Folder:** `examples/demo-a2a/` ✅ implemented

```
User (CLI)
    │  golem agent task-send
    ▼
log-analyzer-001
    │  bash curl → mock-log-service /logs
    │  delegate_to_agent("report-writer-001", findings)
    ▼
report-writer-001
    │  bash date
    │  produces Markdown incident report
    ▼
  task result visible on both agents
```

**The moment the audience remembers:**
> One CLI command. Two agents collaborate autonomously without any human coordination.
> The Log Analyzer never writes the report. The Report Writer never touches the logs.
> Each agent does exactly one thing — and `golem agent tasks` shows the full delegation
> chain on both sides.

**Deploy:**
```bash
# 1 — deploy the mock log service
examples/demo-a2a/mock-log-service/deploy.sh
kubectl port-forward -n demo-a2a svc/mock-log-service 8080:8080 &
curl http://localhost:8080/logs | python3 -m json.tool | head -20
# → 20 healthy INFO entries

# 2 — deploy both agents (~20 seconds)
examples/demo-a2a/deploy.sh
golem agent status --id report-writer-001   # → running
golem agent status --id log-analyzer-001    # → running
```

**Live demo sequence:**
```bash
# inject errors into the mock service
curl -X POST "http://localhost:8080/admin/inject-errors?count=15"
# → {"injected": 15, "error_mode": true}

# trigger the pipeline with ONE command
golem agent task-send --agent log-analyzer-001 \
  --message "Analyse the application logs and produce a formal incident report." \
  --wait --timeout 300

# inspect the delegation chain
golem agent tasks --agent log-analyzer-001   # source=golem-cli → completed
golem agent tasks --agent report-writer-001  # source=a2a       → completed

# read the final report
golem agent task-get --agent log-analyzer-001 --task <task_id>

# restore the service
curl -X POST http://localhost:8080/admin/clear-errors
```

**Why it is impressive:**

| What the audience sees | What it demonstrates |
|---|---|
| One CLI command triggers a 2-agent pipeline | A2A delegation — agents calling agents |
| Log Analyzer never writes the report | Clean separation of responsibilities |
| Report Writer never touches logs | Each agent does exactly one thing |
| Task visible on both agents independently | Full observability of multi-agent execution |
| Each agent is an isolated K8s pod | Real distributed system, not a monolith |
| Zero code — only `AGENTS.md` + `config.yaml` | Configuration-driven multi-agent intelligence |

**Teardown:**
```bash
golem agent delete --id log-analyzer-001
golem agent delete --id report-writer-001
kubectl delete namespace demo-a2a
```

**Requires:** `bash` `a2a` `agents-md` `skill-md`

---

## Choosing a Demo

### By audience

| Audience | Best demo |
|---|---|
| Any — first impression | 1 · Bonnie (zero setup, shows the platform in 3 min) |
| Developer / technical | 2 · Fabio (SRE) |
| Knowledge management | 3 · Gianluca (Doc Agent) |
| DevOps / business | 4 · Matteo (Monitor) |
| Technical + business combined | 5 · A2A Pipeline |

### By setup complexity

| Complexity | Demos | What you need |
|---|---|---|
| **Zero setup** | 1 | minikube + golem deployed |
| **Low** | 2 | + Kubernetes MCP server (one `deploy.sh`) |
| **Medium** | 3, 5 | + one MCP server container |
| **Medium + external secret** | 4 | + Slack Incoming Webhook URL |

### Recommended progression

```
First demo ever                →  1 · Bonnie       (zero setup, platform baseline)
First technical audience       →  2 · Fabio         (SRE — tools + K8s MCP)
First knowledge-mgmt audience  →  3 · Gianluca      (doc ingestion → wiki)
First DevOps / business pitch  →  4 · Matteo        (autonomous monitoring + Slack)
Closing wow for any audience   →  5 · A2A Pipeline  (multi-agent collaboration)
```
