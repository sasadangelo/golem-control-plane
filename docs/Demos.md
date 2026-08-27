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
| `conv` | multi-conversation / conversation_id (Week 5) |
| `cron` | background cron/timer triggers (Week 5) |

---

## Demo Index

| # | Name | Tags | Audience | Duration | Wow moment |
|---|---|---|---|---|---|
| 1 | [Fabio — SRE Agent](#1--fabio--sre-agent) | `bash` `http_check` `agents-md` `skill-md` | technical | 5 min | live container introspection |
| 2 | [Angelo — Architect Agent](#2--angelo--architect-agent) | `mcp-fs` `agents-md` `skill-md` `conv` | security / IBM internal | 8 min | interview → complete IBM-standard TRI |
| 3 | [Gianluca — Doc Agent](#3--gianluca--doc-agent) | `mcp-fs` `agents-md` `skill-md` | technical / knowledge mgmt | 5 min | raw files → conversational knowledge surface |
| 4 | [Matteo — Monitor Agent](#4--matteo--monitor-agent) | `http_check` `agents-md` `skill-md` `cron` | devops / business | 5 min | monitors endpoints forever, alerts on failure |

---

## Demos

---

### 1 · Fabio — SRE Agent

**Persona:** Fabio, Senior Site Reliability Engineer.
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

### 2 · Angelo — Architect Agent

**Persona:** Angelo, IBM Architect, Security & Compliance Analyst.
Interviews a service owner about a new service through a structured 12-question protocol,
then generates a complete IBM-standard Technical Requirements Interlock (TRI) document
and saves it via MCP filesystem.

**Files:** `examples/demo-architecture/` ✅ implemented

**The moment the audience remembers:**
> The service owner answers 12 questions in natural language. Angelo generates a complete
> IBM-standard TRI — every section filled, every table populated — and writes it to disk.
> What used to take 2 days of back-and-forth with the security team takes 8 minutes.

**Demo conversation:**
```
Hi Angelo, I need to onboard a new service.

[Angelo conducts structured 12-question interview:]
  Q1  Service name & purpose
      → "PaymentGateway — handles PCI-DSS card transactions for IBM TLS clients"

  Q2  Ownership
      → "PM: Anna Rossi — Dev: Luca Bianchi"

  Q3  TRI approvers & reviewers
      → "Approver: sec-review@ibm.com — Reviewer: platform@ibm.com"

  Q4  Assumptions
      → "Access to PostgreSQL on IBM Cloud, Stripe API, IBM AppID"

  Q5  Success metrics
      → "95% of transactions < 2s, zero plain-text card data, SOC2 compliant"

  Q6  Architecture & AI
      → "Two Python microservices. Uses IBM Granite 3.8B via WatsonX for fraud detection."

  Q7  Trust zones
      → "Kubernetes Cluster, IBM Cloud Services, Internet (API Connect)"

  Q8  Interfaces & endpoints
      → "POST /payments — public, IBM API Connect, OAuth2 AppID"

  Q9  Data flows
      → "Client → API Connect: HTTPS TLS 1.3, card token, classification: client-SPI"

  Q10 Datastores
      → "PostgreSQL: transaction logs, AES-256, Key Protect, 7-year retention"

  Q11 External dependencies
      → "IBM AppID, API Connect, Stripe API, Secrets Manager, Key Protect"

  Q12 Reliability & operations
      → "2 replicas/2 AZs, OnePipeline CI/CD, PagerDuty. Risk: Stripe egress via Calico."

[Angelo reads TRI-template.md via MCP filesystem]
[Angelo generates complete IBM-standard TRI — all sections filled]
[Angelo writes TRI to /data/tri-output/ via MCP filesystem]

  ✅ Phase 2 complete — TRI generated for PaymentGateway
  ✅ Phase 3 complete — TRI saved to /data/tri-output/TRI-PaymentGateway-2026-08.md
```

**Why it is impressive:**
- Replaces 2 days of manual work with an 8-minute conversation
- The TRI follows the exact IBM standard — `SKILL.md` encodes the protocol, not the LLM's memory
- Every section is filled: trust zones, data flows, datastores, AI considerations — all populated
- The agent reads the template from disk via MCP — the output is traceable and auditable
- One CLI command deploys the agent; `golem agent delete` tears it down cleanly

**Setup:** MCP filesystem server mounted at `/data/tri-templates` with `TRI-template.md`.
Output directory at `/data/tri-output` writable by Angelo.

**Requires:** `mcp-fs` `agents-md` `skill-md` `conv`

---

### 3 · Gianluca — Doc Agent

**Persona:** Gianluca, Document Ingestion & Knowledge Agent.
Accepts document ingestion, sends extracted knowledge through an LLM Wiki MCP flow, saves it
into a wiki, then lets you converse with that document corpus.

**The moment the audience remembers:**
> You upload a product manual, a policy PDF, and a design note. Gianluca ingests them, pushes
> the structured knowledge into a wiki automatically, then answers detailed questions as if
> the documentation had always been organized that way.

**Demo questions:**
```
Create a document agent for this workspace.
Ingest these documents into your knowledge base.
Use the LLM Wiki MCP to extract and structure the content, then save it into the wiki.
Now tell me:
- what are the key concepts across these documents?
- where do they disagree or overlap?
- answer this question only using the ingested docs: how does the system handle failures?
Show me the wiki page structure you created.
```

**Why it is impressive:**
- Shows end-to-end document ingestion, knowledge extraction, and persistence into a wiki
- The audience sees the jump from raw files to a conversational knowledge surface without manual curation
- The same wiki is queryable across multiple conversations — `conv` keeps each session isolated

**Requires:** `mcp-fs` `agents-md` `skill-md`

---

### 4 · Matteo — Monitor Agent

**Persona:** Matteo, Uptime & Reliability Monitor.
Continuously polls a set of HTTP endpoints on a configurable schedule, tracks their status
over time, and raises structured alerts when a failure is detected.

**The moment the audience remembers:**
> You tell Matteo which endpoints to watch. You come back 5 minutes later and find a structured
> alert already waiting — he detected the failure, classified its severity, and logged it
> autonomously while nobody was watching.

**Demo questions:**
```
Who are you and what can you monitor?
Start monitoring https://httpstat.us/200 every 30 seconds and alert me if it goes down.
Now also watch https://httpstat.us/500 — that one is already failing.
Give me a status report of all endpoints you are currently monitoring.
Stop monitoring the 500 endpoint and summarise what you observed.
```

**Expected output shape:**
```markdown
## Uptime Report — Matteo Monitor Agent

### Monitored Endpoints (2)

| Endpoint | Status | Last Check | Latency |
|---|---|---|---|
| https://httpstat.us/200 | ✅ UP   | 14:03:22 | 112 ms |
| https://httpstat.us/500 | ❌ DOWN | 14:03:24 | 98 ms  |

### Alerts (1 active)

**⚠️ ALERT — https://httpstat.us/500**
- First failure: 14:00:01
- Consecutive failures: 6
- HTTP status returned: 500 Internal Server Error
- Recommended action: investigate upstream service

### Summary
1 of 2 endpoints is currently unreachable.
```

**Why it is impressive:**
- The agent keeps running and checking on its own schedule — no human polling required
- The alert format is identical every time (`SKILL.md` defines the protocol)
- `cron` triggers show the platform's background automation capability with zero extra infrastructure

**Requires:** `http_check` `agents-md` `skill-md` `cron`

---

## Choosing a Demo

### By audience

| Audience | Best demo |
|---|---|
| Developer / technical | 1 · Fabio (SRE) |
| Security / IBM internal | 2 · Angelo (TRI) |
| Knowledge management | 3 · Gianluca (Doc Agent) |
| DevOps / business | 4 · Matteo (Monitor) |
| Mixed / first impression | 1 · Fabio — works with zero external setup |

### By setup complexity

| Complexity | Demos | What you need |
|---|---|---|
| **Zero setup** (works today) | 1, 4 | just minikube + golem deployed |
| **Low** (one MCP server) | 3 | + one MCP filesystem server container |
| **Medium** (MCP + templates) | 2 | + MCP filesystem server + TRI-template.md |

### Recommended progression

```
First demo ever               →  1 · Fabio    (zero setup, immediate wow)
First IBM audience (security) →  2 · Angelo   (TRI — hits a real pain)
First knowledge mgmt audience →  3 · Gianluca (doc ingestion → wiki)
First DevOps / business pitch →  4 · Matteo   (autonomous monitoring)
```
