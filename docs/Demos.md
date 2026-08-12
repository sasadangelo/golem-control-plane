# Golem — Demo Catalogue

A living catalogue of high-impact demos. Each entry is self-contained: what it shows, why it is
impressive, what it requires, and what the audience remembers after leaving the room.

Demos are tagged by the platform features they require so you can pick one based on what is
currently deployed.

---

## Feature Tags

| Tag | Meaning |
|---|---|
| `bash` | embedded bash tool (available from Week 3) |
| `http_check` | embedded HTTP health-check tool (available from Week 3) |
| `agents-md` | AGENTS.md persona injection (Week 4) |
| `skill-md` | SKILL.md protocol injection (Week 4) |
| `mcp-fs` | MCP filesystem server |
| `mcp-pg` | MCP PostgreSQL server |
| `mcp-git` | MCP Git server |
| `mcp-github` | MCP GitHub / GitHub Enterprise server |
| `a2a` | A2A agent-to-agent delegation (Week 5) |
| `conv` | multi-conversation / conversation_id (Week 5) |
| `cron` | background cron/timer triggers (Week 5) |
| `webhook` | inbound webhook trigger — receives external HTTP POST (Week 5) |
| `mcp-slack` | MCP Slack server — sends messages to Slack channels |

---

## Demo Index

| # | Name | Tags | Audience | Duration | Wow moment |
|---|---|---|---|---|---|
| 1 | [Aria — SRE Agent](#1--aria--sre-agent) | `bash` `http_check` `agents-md` `skill-md` | technical | 5 min | live container introspection |
| 2 | [Rex — Security Auditor](#2--rex--security-auditor) | `bash` `agents-md` `skill-md` | security / technical | 5 min | autonomous audit with severity classification |
| 3 | [Pulse — Uptime Monitor](#3--pulse--uptime-monitor) | `http_check` `agents-md` `skill-md` `cron` | devops / business | 5 min | monitors endpoints forever, alerts on failure |
| 4 | [Nova — Release Readiness](#4--nova--release-readiness) | `bash` `http_check` `agents-md` `skill-md` | devops / management | 4 min | binary READY / NOT READY verdict with evidence |
| 5 | [Iris — DB Analyst](#5--iris--db-analyst) | `mcp-pg` `agents-md` `skill-md` | business / data | 5 min | SQL from natural language on a real database |
| 6 | [Max — Git Historian](#6--max--git-historian) | `mcp-git` `mcp-fs` `agents-md` `skill-md` | dev / architect | 5 min | CHANGELOG and risk analysis from real commits |
| 7 | [Leo — Service Onboarding](#7--leo--service-onboarding) | `mcp-fs` `mcp-github` `agents-md` `skill-md` `conv` | dev / platform | 6 min | interview → Dockerfile + repo + PR in 60 seconds |
| 8 | [Sage — TRI & Threat Model](#8--sage--tri--threat-model) | `mcp-fs` `mcp-github` `agents-md` `skill-md` `conv` | security / IBM internal | 8 min | interview → TRI + Threat Model + GHE PR |
| 9 | [Duo — Incident Pipeline](#9--duo--incident-pipeline) | `bash` `http_check` `a2a` `agents-md` `skill-md` | technical / CTO | 6 min | two agents cooperate live: watcher delegates to reporter |
| 10 | [Triad — Engineering Health Report](#10--triad--engineering-health-report) | `mcp-pg` `mcp-fs` `a2a` `agents-md` `skill-md` | executive / CTO | 8 min | one question → three agents → one board-ready report |
| 11 | [Healer — Self-Healing Operator](#11--healer--self-healing-operator) | `bash` `http_check` `webhook` `skill-md` `agents-md` `mcp-slack` | platform / ops / IBM | 6 min | Sysdig fires → agent executes runbook → resolves without waking anyone |

---

## Demos

---

### 1 · Aria — SRE Agent

**Persona:** Aria, Senior Site Reliability Engineer.
Probes endpoints, inspects the container environment, produces structured incident reports.

**Files:** `examples/demo-sre/` ✅ already implemented

**The moment the audience remembers:**
> You ask "give me a full environment report" and the agent runs 8 bash commands autonomously,
> redacts secrets, and returns a structured Markdown report — hostname, memory, disk, mounted
> files, running processes — all from inside a live Kubernetes pod.

**Demo questions:**
```
Who are you and what can you do?
Check if https://google.com is reachable and give me a structured report.
Probe the runner's own health endpoint and tell me if this pod is healthy.
Give me a full environment report: resources, mounted files, running processes.
WatsonX might be unreachable. Check https://us-south.ml.cloud.ibm.com, then check
memory and disk, and tell me if this pod is healthy enough for production traffic.
```

**Why it is impressive:**
- The agent knows its name, role, and constraints from `AGENTS.md` — not from the system prompt
- Every report has the same structure every time — `SKILL.md` makes it repeatable, not improvised
- Real tool calls, real output, real K8s pod — not a simulation

**Requires:** `bash` `http_check` `agents-md` `skill-md`

---

### 2 · Rex — Security Auditor

**Persona:** Rex, Container Security Analyst.
Scans the container for security issues and produces a classified findings report.

**The moment the audience remembers:**
> You ask "audit this container" and Rex autonomously runs 8 bash commands — SUID files,
> world-writable dirs, exposed env vars, open ports, suspicious processes — and returns a
> report with HIGH / MEDIUM / LOW severity findings.

**Demo questions:**
```
Who are you?
Perform a full security audit of this container.
Check if there are any world-writable directories under /app.
List all environment variables and flag anything that looks like a secret or credential.
Are there any SUID binaries in this container?
Give me your final security verdict: is this container safe to run in production?
```

**Why it is impressive:**
- The LLM reasons about security findings autonomously — but the report format is always
  identical because `SKILL.md` defines the protocol
- Secrets are automatically redacted (`AGENTS.md` constraint) — audience sees `[REDACTED]`
  appear in the output without anyone having programmed that logic explicitly

**Requires:** `bash` `agents-md` `skill-md`

---

### 3 · Pulse — Uptime Monitor

**Persona:** Pulse, Uptime & Availability Monitor.
Continuously monitors a list of endpoints, alerts on failure, tracks degradation over time.

**The moment the audience remembers:**
> You tell Pulse to monitor 5 URLs every 30 seconds. You then deliberately break one
> (httpstat.us/500). Pulse detects it on the next cycle and produces an alert — without
> anyone asking.

**Demo questions:**
```
Monitor these services every 30 seconds and alert me if any of them goes down:
- https://google.com
- https://github.com
- https://httpstat.us/200
- https://httpstat.us/500
Start monitoring. I will wait.
[wait 30s — Pulse detects the 500 and reports autonomously]
The previous check flagged httpstat.us/500. Investigate further and tell me what
the on-call engineer should do right now.
```

**Why it is impressive:**
- Background cron trigger — the agent does something without being asked, then reports back
- Shows the platform is not just a chatbot but an autonomous operator that keeps running

**Requires:** `http_check` `agents-md` `skill-md` `cron`

---

### 4 · Nova — Release Readiness

**Persona:** Nova, Release Readiness Engineer.
Runs a pre-deployment checklist and returns a binary READY / NOT READY verdict.

**The moment the audience remembers:**
> The output ends with a green ✅ READY FOR DEPLOYMENT or a red ❌ BLOCKED — 3 blockers found.
> Every time. Same structure. No improvisation.

**Demo questions:**
```
Who are you?
Run a pre-deployment readiness check for this container.
We are going live in 10 minutes. Is this pod ready for production traffic?
One of the checks failed. What do I need to fix before we can deploy?
```

**Expected output shape:**
```markdown
## Release Readiness Report — order-service

**Verdict: ✅ READY FOR DEPLOYMENT**

### Checks (5/5 passed)
- ✅ Config present at /app/config.yaml
- ✅ Health endpoint: HTTP 200 in 34ms
- ✅ WatsonX endpoint reachable
- ✅ Memory: 780Mi available
- ✅ No unexpected processes

### Recommendations
No blockers. Safe to proceed.
```

**Why it is impressive:**
- The binary verdict (READY / NOT READY) is what a manager sees — not a wall of text
- The checklist is defined in `SKILL.md` — it never changes, never forgets a step

**Requires:** `bash` `http_check` `agents-md` `skill-md`

---

### 5 · Iris — DB Analyst

**Persona:** Iris, Data & Analytics Engineer.
Queries a real PostgreSQL database in natural language and produces structured analytical reports.

**The moment the audience remembers:**
> You ask "what are the top 5 slowest API endpoints in the last 24 hours?" — no SQL, no
> code. Iris writes the query, executes it against a real database, and returns a formatted
> table with analysis and recommendations.

**Demo questions:**
```
Who are you and what database do you have access to?
What are the top 5 slowest API endpoints in the last 24 hours?
Are there any users with more than 50 failed login attempts today? Flag them as suspicious.
Give me a daily active users trend for the last 7 days as a table.
Which API endpoints returned HTTP 500 more than 10 times this week?
Summarise the overall health of this application based on what you see in the data.
```

**Why it is impressive:**
- Real database, real data, real SQL — the audience can verify the numbers
- The agent writes SQL it has never seen before based on the schema it discovers via MCP
- The final "overall health" summary shows multi-step reasoning: multiple queries, then synthesis

**Setup:** spin up a PostgreSQL container with a realistic demo dataset
(API access logs: endpoint, status_code, duration_ms, user_id, timestamp).

**Requires:** `mcp-pg` `agents-md` `skill-md`

---

### 6 · Max — Git Historian

**Persona:** Max, Engineering Intelligence Analyst.
Reads a real Git repository and produces changelogs, risk assessments, and contribution summaries.

**The moment the audience remembers:**
> You point Max at your actual codebase. You ask "what changed in the last 10 commits?"
> and get a plain-English summary that a non-technical manager can read. Then you ask
> "which commits touched security-sensitive files?" and get a risk-classified list.

**Demo questions:**
```
Who are you?
Summarise the last 10 commits in plain English — one line each.
Which commits in the last month touched authentication, secrets, or payment code?
Generate a CHANGELOG.md entry for the v1.2.0 release based on the commits since v1.1.0.
Who are the top 3 contributors this month and what areas did they work on?
Is there any commit that looks risky or unusual? Explain why.
```

**Why it is impressive:**
- Works on any real repo — the audience can point it at their own code
- The CHANGELOG has a fixed format every time (SKILL.md) — it is a production tool, not a demo trick
- The risk assessment shows the agent reasoning about what is security-sensitive — without
  being given a list of sensitive files

**Requires:** `mcp-git` `mcp-fs` `agents-md` `skill-md`

---

### 7 · Leo — Service Onboarding

**Persona:** Leo, Platform Engineering Assistant.
Interviews a developer about a new service and generates all the boilerplate in one shot:
Dockerfile, repo structure, health check, K8s manifests — then opens a PR on GitHub Enterprise.

**The moment the audience remembers:**
> The developer answers 5 questions. Leo generates a complete, production-quality repo layout
> and opens a PR on GitHub Enterprise — in under 60 seconds. The PR is real, reviewable,
> and mergeable.

**Demo conversation:**
```
Hi Leo, I need to onboard a new service.

[Leo asks:]
  What is the service name?               → "payment-gateway"
  What language / framework?              → "Python, FastAPI"
  What port does it listen on?            → "8080"
  External dependencies?                  → "PostgreSQL, Redis, IBM AppID"
  Should I create a new GitHub repo?      → "yes, under org/backend-services"

[Leo generates and pushes:]
  ✅ Repo created: github.ibm.com/org/backend-services/payment-gateway
  ✅ Dockerfile (Python 3.12, uv, non-root user, health check)
  ✅ src/ layout with FastAPI skeleton + /health endpoint
  ✅ k8s/deployment.yaml + service.yaml + configmap.yaml
  ✅ .github/workflows/ci.yaml skeleton
  ✅ PR #1 opened — ready for review
```

**Why it is impressive:**
- The dev wrote zero boilerplate — only answered questions
- The output is not Lorem Ipsum — it is real, working code tailored to the declared stack
- The PR is on a real GitHub Enterprise instance — reviewable immediately

**Setup:** a GitHub Enterprise org with a test group where Leo has write access.

**Requires:** `mcp-fs` `mcp-github` `agents-md` `skill-md` `conv`

---

### 8 · Sage — TRI & Threat Model

**Persona:** Sage, IBM Security & Compliance Analyst.
Interviews a service owner about a new service, generates a TRI (Technical Risk Inventory)
and a Threat Model following IBM standards, then opens a PR on GitHub Enterprise.

**The moment the audience remembers:**
> A service owner answers 8 questions in natural language. Sage generates two complete
> IBM-standard documents — TRI and Threat Model — and opens a PR on the security-docs repo.
> What used to take 2 days of back-and-forth with the security team takes 4 minutes.

**Demo conversation:**
```
Hi Sage, I need to onboard a new service through the security review process.

[Sage asks:]
  Service name and purpose?
  → "PaymentGateway — handles PCI-DSS card transactions"

  Does it process, store, or transmit personal or financial data?
  → "Yes — tokenised card numbers, transaction amounts"

  External dependencies? (APIs, databases, third-party services)
  → "PostgreSQL, Stripe API, IBM AppID"

  Authentication mechanism?
  → "IBM AppID OAuth2, service-to-service via mTLS"

  Deployment environment?
  → "IBM Cloud Kubernetes, us-south region"

  Is it internet-facing?
  → "Yes, public API behind IBM API Connect"

  Data retention policy?
  → "Transaction logs 7 years (regulatory requirement)"

  Existing security controls?
  → "WAF, DDoS protection via IBM Cloud Internet Services"

[Sage reads existing TRI/TM examples via MCP filesystem]
[Sage generates documents in IBM standard format]
[Sage pushes to GitHub Enterprise via MCP GitHub]

  ✅ TRI-PaymentGateway.md generated (12 risk items identified, 3 HIGH)
  ✅ ThreatModel-PaymentGateway.md generated (STRIDE analysis, 8 threats)
  ✅ PR #47 opened: github.ibm.com/org/security-docs/pull/47
     Branch: security/tri-payment-gateway-2026-08
     Reviewers: @security-team auto-assigned
```

**Why it is impressive:**
- Replaces 2 days of manual work with a 4-minute conversation
- Documents follow the exact IBM standard — because `SKILL.md` encodes the protocol
- The PR is real, on the real GHE security-docs repo — the security team can review immediately
- The agent identifies HIGH risk items autonomously (PCI-DSS data + internet-facing = flag)

**Setup:** 2-3 anonymised TRI and Threat Model examples in a local directory (MCP filesystem).
A GitHub Enterprise repo `security-docs` where Sage has write access.

**Requires:** `mcp-fs` `mcp-github` `agents-md` `skill-md` `conv`

---

### 9 · Duo — Incident Pipeline

**Persona:** two cooperating agents — `Watcher` (monitors) and `Reporter` (documents).

**The moment the audience remembers:**
> Nobody sends a message. Watcher detects a 500 on its own after 30 seconds and
> delegates an incident report to Reporter via A2A. The audience watches the task
> lifecycle go `submitted → working → completed` in real time on the CLI. Two agents,
> zero human intervention.

**Setup:**
```bash
# Deploy both agents
golem agent create --config watcher/config.yaml ...
golem agent create --config reporter/config.yaml ...

# Tell Watcher to start
golem chat --id watcher
> Monitor https://httpstat.us/500 every 20 seconds.
  If it returns a non-2xx status, delegate an incident report to reporter-001.

# Open a second terminal — watch task lifecycle
golem agent tasks --agent reporter-001 --watch

# Wait 20 seconds — Watcher detects the 500
# Reporter receives the A2A task, writes the report
# Audience sees: submitted → working → completed
```

**Why it is impressive:**
- No human triggers the incident — the system detects it autonomously
- The A2A task lifecycle is visible on the CLI — it is not magic, it is observable
- Two isolated K8s pods cooperating via a defined protocol — this is the core of the platform

**Requires:** `bash` `http_check` `a2a` `agents-md` `skill-md` `cron`

---

### 10 · Triad — Engineering Health Report

**Persona:** three cooperating agents — `Cortex` (orchestrator), `Iris` (DB analyst),
`Max` (Git analyst).

**The moment the audience remembers:**
> A CTO types one sentence. Three agents coordinate, query real data sources, and produce
> a board-ready Engineering Health Report in under 2 minutes. The CTO's team used to spend
> half a day assembling this manually every week.

**Demo:**
```bash
golem chat --id cortex
> Give me this week's engineering health report.
```

**What happens internally (visible via `golem agent tasks`):**
```
Cortex delegates to Iris:
  → "Query the API logs DB: error rate, top 5 slowest endpoints, anomalies this week"
  ← Report section: Operational Health

Cortex delegates to Max:
  → "Analyse commits this week: volume, risk, areas changed, contributors"
  ← Report section: Code Quality & Velocity

Cortex aggregates + produces:

## Weekly Engineering Health Report — W32 2026

### Operational Health  (by Iris)
- Error rate: 0.3% (↓ from 0.8% last week) ✅
- Slowest endpoint: POST /payments/process — avg 1.2s ⚠️
- Anomaly detected: spike in 401s on Tuesday 14:00–15:00

### Code Quality & Velocity  (by Max)
- 47 commits by 8 contributors
- 3 commits touched authentication code — manual review recommended
- No commits to payment processing this week ✅

### Recommendations
1. Investigate POST /payments/process latency — 1.2s exceeds SLA threshold
2. Review the 3 auth commits from @dev-a before next release
3. Root-cause the Tuesday 401 spike — possible token expiry issue
```

**Why it is impressive:**
- One question, three agents, two real data sources, one coherent document
- The CTO sees exactly what they need — no data wrangling, no SQL, no git log
- The report has the same structure every week (SKILL.md) — it is a production tool

**Requires:** `mcp-pg` `mcp-fs` `mcp-git` `a2a` `agents-md` `skill-md`

---

### 11 · Healer — Self-Healing Operator

**Persona:** Healer, Platform Reliability Operator.
Receives alerts from Sysdig via webhook, executes the appropriate runbook autonomously,
verifies the fix, and only escalates to the on-call engineer if it cannot resolve the problem.

**The moment the audience remembers:**
> A Sysdig alert fires. Nobody types anything. Healer receives the webhook, identifies the
> problem type, executes the runbook step by step, verifies the fix, and posts to Slack:
> *"CrashLoopBackOff on order-service resolved automatically — restarted 1 pod, healthy in 34s.
> No action required."* The on-call engineer was never woken up.

**The pain it solves:**
Today the flow is: Sysdig → OCM (integration to maintain) → runbook (someone reads it manually)
→ on-call engineer paged 24/7, even for trivial issues.
Golem removes OCM as a middleware and executes the runbook autonomously. The engineer is paged
only when the agent fails to resolve — and receives full context, not just a raw alert.

**Demo setup:**
```bash
# Deploy Healer — permanently running (mode: shared or stateful)
golem agent create \
  --config  examples/demo-healer/config.yaml \
  --agents-md examples/demo-healer/AGENTS.md \
  --skill   examples/demo-healer/runbook-crashloop.md \
  --skill   examples/demo-healer/runbook-oom.md \
  --skill   examples/demo-healer/runbook-endpoint-down.md

# Configure Sysdig to POST alerts to:
# http://<golem-cp>:9000/agents/healer-001/webhook
```

**Demo flow (live on stage):**
```bash
# Terminal 1 — show Healer is alive and waiting
golem chat --id healer-001
> Who are you and what runbooks do you know?

# Terminal 2 — simulate a Sysdig alert (CrashLoopBackOff)
curl -X POST http://localhost:9000/agents/healer-001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert": "CrashLoopBackOff",
    "severity": "HIGH",
    "namespace": "prod",
    "pod": "order-service-7d9f8b-xk2p",
    "message": "Container order-service has been restarting for 5 minutes"
  }'

# Terminal 1 — Healer wakes up and executes the runbook autonomously:
```

**What the audience sees Healer do (no human input):**
```
[Healer receives webhook — CrashLoopBackOff on order-service]

Step 1 — Gather context
  → bash: kubectl get pod order-service-7d9f8b-xk2p -n prod -o json
  → bash: kubectl logs order-service-7d9f8b-xk2p -n prod --previous --tail=50
  Finding: OOMKilled in previous container — memory limit hit

Step 2 — Attempt fix (runbook: crashloop → check logs → if OOM → increase limit or restart)
  → bash: kubectl rollout restart deployment/order-service -n prod
  → bash: kubectl rollout status deployment/order-service -n prod

Step 3 — Verify
  → http_check: http://order-service.prod.svc.cluster.local/health
  Result: HTTP 200 in 28s ✅

Step 4 — Notify (resolved — no escalation needed)
  → MCP Slack: #platform-alerts
    "✅ AUTO-RESOLVED — CrashLoopBackOff on order-service (prod)
     Root cause: OOMKilled (previous container hit memory limit)
     Action taken: rollout restart — pod healthy in 28s
     Recommendation: review memory limits before next deploy
     No on-call page sent."
```

**Escalation path (when Healer cannot fix it):**
```
Step 3 — Verify
  → http_check: http://order-service.prod.svc.cluster.local/health
  Result: connection refused after 120s ❌

Step 4 — Escalate
  → MCP Slack: #platform-alerts  (+ @oncall)
    "⚠️ ESCALATION REQUIRED — order-service (prod) — unresolved after 2 minutes
     Alert: CrashLoopBackOff
     Tried: rollout restart — pod still not healthy
     Logs: [last 50 lines attached]
     Pod status: CrashLoopBackOff (exit code 137 — OOMKilled repeatedly)
     Suggested next step: increase memory limit in deployment.yaml
     Runbook: runbook-oom.md"
```

**Why it is impressive:**
- Sysdig → Golem directly — no OCM, no middleware to maintain
- The runbook is a `SKILL.md` — the same document the engineer would read, now executed by the agent
- The on-call engineer is paged only for unresolved issues, and receives full context not a raw alert
- The agent reasons about the logs to identify root cause — not just blindly restarting
- Completely autonomous — zero human input from alert to resolution

**For an IBM audience specifically:**
- Replaces the OCM integration layer entirely
- Works with any alerting system that can POST a webhook (Sysdig, PagerDuty, Prometheus Alertmanager)
- The runbooks you already have become SKILL.md files — zero rewrite

**Setup:**
- A running Kubernetes cluster with a test deployment to break
- Sysdig (or a simple curl to simulate) configured to POST to the Golem webhook endpoint
- MCP Slack server (or omit for the demo — just show the Slack message as text output)
- 2-3 runbook SKILL.md files (can be simplified versions of real runbooks)

**Requires:** `bash` `http_check` `webhook` `skill-md` `agents-md` `mcp-slack`

---

## Choosing a Demo

### By audience

| Audience | Best demo |
|---|---|
| Developer | 6 · Max (Git), 7 · Leo (Onboarding) |
| DevOps / Platform | 1 · Aria (SRE), 4 · Nova (Release), 9 · Duo (Incident) |
| Security team | 2 · Rex (Audit), 8 · Sage (TRI/TM) |
| Data / Business | 5 · Iris (DB Analyst) |
| Management / CTO | 4 · Nova, 9 · Duo, 10 · Triad |
| IBM internal — security | 8 · Sage (TRI/TM) — most IBM-specific pain point |
| IBM internal — platform/ops | 11 · Healer (Self-Healing) — replaces OCM, eliminates 3am pages |
| Mixed / first impression | 1 · Aria — works with zero external setup |

### By setup complexity

| Complexity | Demos | What you need |
|---|---|---|
| **Zero setup** (works today) | 1, 2, 4 | just minikube + golem deployed |
| **Low** (one MCP server) | 3, 5, 6 | + one MCP server container |
| **Medium** (MCP + GHE token) | 7, 8 | + GHE access + example templates |
| **Medium** (webhook + runbooks) | 11 | + Week 5 webhook trigger + runbook SKILL.md files |
| **High** (multi-agent + data) | 9, 10 | + A2A (Week 5) + multiple MCP servers |

### Recommended progression

```
First demo ever               →  1 · Aria     (zero setup, immediate wow)
First business audience       →  5 · Iris     (SQL from natural language)
First IBM audience (security) →  8 · Sage     (TRI/TM — hits a real pain)
First IBM audience (ops)      → 11 · Healer   (self-healing — eliminates 3am pages)
First executive pitch         → 10 · Triad    (the full vision)
```
