# Golem — Roadmap

## MVP — 5-Week Sprint  `August–September 2026`

The goal of the MVP is a fully working **Agent-as-a-Service platform** running on any Kubernetes cluster (IBM Cloud, AWS, GCP, or a local Kind cluster).

> Items marked **`[new]`** were added after the initial design review to close the two main gaps: agent cooperation and network isolation.

---

### Week 3 — Chat Router & CLI  `August W3`

**Goal:** End-to-end streaming communication between user and agent, usable from the terminal immediately.

- [x] WebSocket endpoint: `WS /chat/{agent_id}`
- [x] Single ClusterIP gateway proxy — no per-pod Ingress
- [x] Token streaming passthrough from pod to client
- [x] Single conversation per agent: `WS /chat/{agent_id}` carries one implicit conversation (no `conversation_id` yet)
- [x] Single conversation state in-memory (one message list per agent, in the Control Plane process — no external dependency)
- [x] CLI `golem chat --id <agent_id>` — opens the single conversation for that agent
- [x] **`[new]`** A2A task lifecycle records (`submitted → working → completed / failed`)
- [x] **`[new]`** Control Plane as A2A broker: `GET /agents/{id}/card`, peer handshake endpoint

**Deliverable:** `golem chat --id <agent_id>` streams responses live from the sandbox pod — usable immediately from the terminal. ✅

---

### Week 4 — Agent Identity & Behaviour  `August W4`

**Goal:** Transform the runner from a generic chatbot into a real agent with defined identity and repeatable business-logic protocols.

- [ ] `POST /agents` accepts optional `AGENTS.md` upload (`-F "agents_md=@AGENTS.md"`)
- [ ] `POST /agents` accepts one or more `SKILL.md` uploads (`-F "skills=@<name>.md"`) — single `.md` files only at this stage; no scripts, no dependencies
- [ ] Control Plane mounts uploaded files into the pod via ConfigMap: `AGENTS.md` at `/app/AGENTS.md`, each skill at `/app/skills/<name>.md`
- [ ] Runner reads `AGENTS.md` at boot and injects it into the LLM system message as behavioural context (*who the agent is*)
- [ ] Runner indexes available `SKILL.md` files at boot; injects the relevant one lazily per turn (*how to solve a specific class of tasks, step by step, using the available tools*)
- [ ] **`[new]`** `POST /agents` accepts an optional `mcp_servers` list (static URIs); Control Plane stores them in the agent ConfigMap; Runner calls `MultiServerMCPClient` at boot and registers each server's tools into the LangGraph tool node — no registry yet, URI per agent

**Deliverable:** an agent deployed with `AGENTS.md` + `SKILL.md` follows a precise, repeatable business protocol instead of improvising — e.g. "analyse HTTP 500 logs" always produces the same structured output regardless of how the question is phrased.

> **Skill format at this stage:** a skill is a single `SKILL.md` file. No scripts, no dependencies. The folder-based format with scripts is introduced in §2.X.

---

### Week 5 — Automations, A2A Delegation & Persistence  `September W1`

**Goal:** Background tasks, agent cooperation, polished CLI, multi-conversation support, and optional durable persistence.

- [ ] Background tasks in Agent Runner: Cron, Timer, Webhook triggers
- [x] CLI commands: `golem agent create`, `golem agent list`, `golem agent delete`, `golem agent status`, `golem agent config`
- [x] CLI commands: `golem cp add`, `golem cp use`, `golem cp list`, `golem cp remove`, `golem cp status` — multi-context control plane management
- [ ] CLI: `golem agent tasks --agent <id>` — show A2A task lifecycle
- [ ] Helm Chart for Control Plane deployment
- [ ] **`[new]`** A2A `SendMessage` delegation between agents (e.g. `Log-Analyzer` → `Report-Writer`)
- [ ] **`[new]`** Signed Agent Card validation in the Card Registry
- [ ] Multi-conversation support: `WS /chat/{agent_id}?conversation_id=<uuid>` — each conversation isolated
- [ ] Conversation state keyed by `(agent_id, conversation_id)` in-memory
- [ ] CLI conversation management:
  - `golem conv list --agent <id>` — list conversations for an agent
  - `golem conv new --agent <id> [--name <label>]` — start a new conversation
  - `golem conv switch --agent <id> <conv_id>` — resume an existing conversation
  - `golem conv delete --agent <id> <conv_id>` — delete a conversation
- [ ] Message history stored in PostgreSQL (optional — only if time permits; in-memory covers MVP)
- [ ] Agent state persistence in Redis (deferred — real value comes with LangGraph checkpointer in Phase 2)
- [ ] **`[new]`** Conversation history is unbounded in-memory — **known debt**: no cap, no summary; context window overflow is silently truncated by the framework; full rolling-summary strategy deferred to Phase 2 §2.2

**Deliverable:** a multi-agent flow works end-to-end; full conversation management from CLI; platform deployable on any K8s cluster via Helm.

---

## Component × Week Delivery Matrix

| Component | W1 | W2 | W3 | W4 | W5 |
|---|:---:|:---:|:---:|:---:|:---:|
| Agent Runner (Docker + LangGraph) | ✅ | — | — | AGENTS.md + SKILL.md + MCP | Cron |
| A2A Agent Card + inbound tasks **`[new]`** | ✅ | — | ✅ Broker | — | SendMsg |
| Control Plane (FastAPI) | — | ✅ | Chat WS | file upload + ConfigMap | Helm |
| K8s Provisioner (Python k8s-client) | — | ✅ | — | — | — |
| NetworkPolicy + TTL GC **`[new]`** | — | ✅ | — | — | — |
| Single conversation state (in-memory) | — | — | ✅ | — | — |
| A2A task lifecycle + broker **`[new]`** | — | — | ✅ | — | — |
| CLI — `golem chat` | — | — | ✅ | — | — |
| CLI — `cp *` (multi-context control plane) | — | — | — | — | ✅ |
| CLI — `agent create/list/delete/status/config/card` | — | — | — | — | ✅ |
| CLI — `agent tasks` | — | — | — | — | [ ] |
| Multi-conversation + `golem conv *` CLI | — | — | — | — | [ ] |
| Persistence (PostgreSQL + Redis) *(optional)* | — | — | — | — | ✅ |

---

## Concrete MVP Use Cases

### 1. Create a custom agent on the fly

```bash
golem agent create \
  --name "Log-Analyzer" \
  --prompt "Scan application logs for HTTP 500 errors and summarise root causes." \
  --skills read-logs
```

The Control Plane creates an isolated K8s Namespace, spawns the Agent Runner pod with the given prompt, and returns the agent ID in seconds.

---

### 2. Chat with the agent in its sandbox

```bash
golem chat --id log-analyzer-001
> Analyse the last hour of logs and tell me if my application had any issues.
```

The agent executes its skills inside the isolated pod, processes the diagnosis, and streams the response back to the terminal. If the pod crashes, all other agents remain unaffected.

---

### 3. Run background automated tasks

```bash
golem agent schedule \
  --agent log-analyzer-001 \
  --cron "*/30 * * * *" \
  --task "health-check /health"
```

The agent pod continues running autonomously in its sandbox. If the `/health` endpoint fails, it sends a report — no open chat session required.

---

## Post-MVP Milestones

### Phase 2 — Post-MVP Essentials

Items are listed in **priority order** — each one makes the platform observable, resilient, or usable by others before adding new capabilities.

#### 2.1 — Observability first: see what is happening inside

| Item | Repository | Description |
|---|---|---|
| **Observability — Langfuse** | `golem-observability` | Deploy Langfuse as a standalone Docker image in `golem-system`; instrument `golem-framework` LLM Gateway + loop with traces/generations/spans; runner pods emit traces to internal ClusterIP — no internet egress required |

> **Why first:** LLM Gateway and Graph Plugin add capability. Langfuse tells you whether what you already have is working. Without it you are blind — no visibility into why an agent responded badly, how many tokens it consumed, or where in the graph it got stuck. Required before showing the platform to anyone else.

#### 2.2 — Resilience: do not lose state on restart

| Item | Repository | Description |
|---|---|---|
| **LangGraph checkpointer on Redis** | `golem-framework` | Persist graph state at every step to Redis; survive pod restarts, TTL expiry, and human-in-the-loop pauses without losing the conversation |
| Agent state + message history in Redis | `golem-control-plane` | Control Plane persists known sandboxes and chat history to Redis; survives Control Plane restarts |
| **Conversation rolling summary** | `golem-framework` | When a conversation exceeds a configurable threshold (token count or message count), a LangGraph summary node calls the LLM to produce a condensed summary, replaces older messages with a single `SystemMessage("Summary: …")`, and persists the result to Redis — prevents context window overflow and unbounded memory growth. Requires Redis persistence above. |

#### 2.3 — Multi-provider: choose the model per agent

| Item | Repository | Description |
|---|---|---|
| Extract `golem-agent-sdk` | `golem-agent-sdk` | A2A lifecycle, Agent Card, heartbeat, platform identity — **no LLM dependency** |
| Extract `golem-framework` | `golem-framework` | Agentic loop abstraction (LangGraph backend) + LLM Gateway |
| **LLM Gateway — WatsonX** | `golem-framework` | `provider=watsonx`, `protocol=watsonx` — IBM Cloud native SDK |
| **LLM Gateway — Ollama native** | `golem-framework` | `provider=ollama`, `protocol=ollama` — local Ollama REST API |
| **LLM Gateway — Ollama OpenAI-compat** | `golem-framework` | `provider=ollama`, `protocol=openai` — Ollama `/v1` endpoint |
| Thin runner entrypoint | `golem-runner` | Imports `golem-agent-sdk` + `golem-framework`; no embedded logic |

> **LLM Gateway placement rationale:** the gateway lives in `golem-framework`, not `golem-agent-sdk`.
> `golem-agent-sdk` must remain importable by non-LLM agents (A2A proxies, orchestrators).
> Swapping the agentic backend (LangGraph → AutoGen) and swapping the LLM backend (WatsonX → Ollama) are both `golem-framework` concerns and should evolve together.

#### 2.4 — Skill Registry: reusable skills from Git repositories

Skills evolve across three stages — the source changes, but the layout and the Runner behaviour never do:

| Stage | Source | Skill format | Dependency strategy |
|---|---|---|---|
| Week 4 | Local file upload (`-F "skills=@<name>.md"`) | Single `SKILL.md` | None — no scripts |
| Phase 2 §2.4 | Git repository (registered source) | Folder: `SKILL.md` + `scripts/` + `requirements.txt` | `pip install -r requirements.txt` at Runner boot |
| Phase 3 | Git **or** OCI Registry | Same folder layout | Per-skill virtualenv (`/app/skills/<name>/.venv`) — full isolation |

**Skill folder layout (from Phase 2 onwards):**

```
<skill-name>/
├── SKILL.md               # LLM instructions — injected into system message
├── metadata.yaml          # name, version, description, tags, min_golem_version
└── scripts/               # optional — executable tools the agent can invoke
    ├── parse_logs.py
    └── requirements.txt   # pip dependencies declared here
```

**Skill repository layout (Git repo):**

```
agent-skills/              # one Git repo, N skills
├── skills.index.yaml      # repo manifest — lists all skills with name, version, path
├── read-logs/
│   ├── SKILL.md
│   ├── metadata.yaml
│   └── scripts/
│       ├── parse_logs.py
│       └── requirements.txt
└── summarize-report/
    ├── SKILL.md
    └── metadata.yaml
```

**`skills.index.yaml` format:**

```yaml
name: acme-agent-skills
description: "Skills for log analysis and reporting"
maintainer: acme-org
skills:
  - name: read-logs
    version: 1.2.0
    path: read-logs/SKILL.md
    tags: [observability, logs]
  - name: summarize-report
    version: 1.0.3
    path: summarize-report/SKILL.md
    tags: [reporting, markdown]
```

| Item | Repository | Description |
|---|---|---|
| **Skill Registry** | `golem-control-plane` | `POST /skills/sources` registers a named Git repo (name, URI, ref); `GET /skills/sources` lists registered sources; `POST /skills/sources/sync` refreshes the local index from all sources; `GET /skills` lists available skills; `POST /agents` accepts `skills: [name]` — Control Plane resolves name → Git repo → fetches folder → mounts as ConfigMap at `/app/skills/<name>/`; CLI: `golem skill source add / list / remove / sync`, `golem skill list / show` |
| **Runner: folder-aware skill loading** | `golem-runner` | Runner scans `/app/skills/*/SKILL.md` at boot; for each skill with a `scripts/requirements.txt` runs `pip install -r requirements.txt`; indexes skills by name for lazy per-turn injection |

> **Source type abstraction:** the `POST /skills/sources` payload includes a `type` field (`git` \| `oci`). In Phase 2 only `type: git` is implemented. The `OciFetcher` is added in Phase 3 without changing the API or the Runner.

> **Long-term direction → Phase 3:** Skill Marketplace — versioned, signed, public/private catalogue of Git and OCI skill repositories; `golem skill search / install / publish`; per-skill virtualenv isolation; signature verification before the runner mounts any skill.

#### 2.5 — MCP Registry: one catalogue, many agents

| Item | Repository | Description |
|---|---|---|
| **MCP Registry** | `golem-control-plane` | `POST /mcp` registers a named MCP server (name, URI, description, tags); `GET /mcp` lists available servers; `DELETE /mcp/{name}` removes one; `POST /agents` accepts `mcp_servers: [name]` — references resolved by the Control Plane at deploy time, URI injected into the agent ConfigMap; CLI: `golem mcp add / list / remove` |

> **Why here (after §2.3, before §2.6):** Step 1 (Week 4) made MCP work per-agent with a raw URI. The Registry makes the same server reusable across N agents without repeating the URI. Multi-tenancy (§2.6) will then scope Registry entries per-tenant — so the Registry must exist first.

> **Long-term direction → Phase 3:** MCP Marketplace — versioned, signed, public/private catalogue; `golem mcp search / install / publish`; signature verification before the runner mounts any server.

---

#### 2.6 — Programmability: inject custom logic without rebuilding

| Item | Repository | Description |
|---|---|---|
| **Graph Plugin system** | `golem-framework` | `loop/plugin.py` — loads `build_graph()` from `/app/graph/pipeline.py` at boot; `POST /agents` accepts optional `-F "graph=@pipeline.py"`; Control Plane creates a second ConfigMap `runner-graph`; falls back to built-in ReAct loop if no plugin supplied |

#### 2.7 — Multi-tenancy: open to other users

| Item | Repository | Description |
|---|---|---|
| Multi-tenant RBAC (lightweight) | `golem-control-plane` | Per-user API key scoped to a set of sandbox namespaces; no full OAuth required at this stage |

#### 2.8 — Infrastructure

| Item | Repository | Description |
|---|---|---|
| Stateful Sandbox | `golem-control-plane` | PVC-backed agent pod for persistent state across sessions |
| Vault / external secret store | `golem-control-plane` | Replace K8s Secret with External Secrets Operator |
| gVisor / Kata Containers | infra | Runtime isolation for dynamic code execution |
| Go CLI binary | `golem-cli` | Distributable without Python runtime |
| **Provisioner Stage 1** | `golem-control-plane` | `DockerComposeProvisioner` for single-machine dev; `OpenShiftProvisioner` extending `KubernetesProvisioner` |

#### 2.9 — Multi-context CLI (kubectl-style)

| Item | Repository | Description |
|---|---|---|
| **Multi-context support** | `golem-cli` | `~/.golem/config.yaml` with named contexts (name, url, token); `golem context list/add/use/delete`; all commands resolve the active context automatically — zero breaking change to existing interface |

---

### Phase 3 — Ecosystem Expansion

| Item | Repository | Description |
|---|---|---|
| **Skill Marketplace** | `golem-control-plane` | Versioned, signed, public/private catalogue of Skill repositories (Git and OCI); `golem skill search / install / publish`; semantic versioning + signature verification before the runner mounts any skill; per-skill virtualenv isolation (`/app/skills/<name>/.venv`) — full dependency isolation; builds on the Skill Registry introduced in §2.4 |
| **MCP Marketplace** | `golem-control-plane` | Versioned, signed, public/private registry of MCP servers; `golem mcp search / install / publish`; semantic versioning + signature verification before the runner mounts any server; builds on the MCP Registry introduced in §2.5 |
| **OCI Skill source support** | `golem-control-plane` | `type: oci` in `POST /skills/sources`; `OciFetcher` pulls skill bundles from an OCI registry (`oci://registry.example.com/skills/<name>:<version>`); same folder layout as Git-sourced skills; recommended when skills carry heavy script dependencies |
| `golem-framework` AutoGen backend | `golem-framework` | `loop/autogen.py` — swap LangGraph for AutoGen |
| `golem-framework` CrewAI backend | `golem-framework` | `loop/crewai.py` — swap LangGraph for CrewAI |
| **LLM Gateway — OpenAI** | `golem-framework` | `provider=openai`, `protocol=openai` — public OpenAI API or any OpenAI-compat endpoint |
| Graph plugin code signing | `golem-control-plane` | Sign `pipeline.py` at upload time; runner verifies signature before `exec`; OPA policy validation |
| Multi-tenant isolation + RBAC | `golem-control-plane` | Per-tenant namespacing and API key scoping |
| **Provisioner Stage 2 — IAL** | `golem-control-plane` | Infrastructure Profiles (named bundles of backend + quota + NetworkPolicy) selectable via `PROVISIONER_BACKEND` |
| **Provisioner Stage 3 — Operator** | `golem-operator` | `GolemAgent` CRD + Kubernetes Operator for GitOps-style agent management (coexists with REST API) |
| Web UI for agent management | `golem-ui` | React dashboard for agent lifecycle and A2A task monitoring |
