# Golem — Roadmap

> **Working constraint:** ~1 hour/day with AI assistance (~20 effective hours/month).
> Each MVP is scoped to fit within that budget — **max ~18 usable hours** per month
> (accounting for context-switching and review time).
> The selection criterion for each MVP: *minimum work that unlocks a new wow demo.*
>
> **Personal assistant note:** Golem is already usable as a local personal assistant today
> via `MockProvisioner` (control plane + runner as plain Python processes, no K8s).
> MVP 2 adds `ProcessProvisioner` (zero deps — just Python, no Docker, no K8s).
> MVP 4 adds `DockerProvisioner` (`docker compose up` — one command on any machine).

---

## MVP 1 ✅ Delivered  `August 2026`

The MVP delivered a fully working **Agent-as-a-Service platform** running on Kubernetes.

| Area | What was delivered |
|---|---|
| **Agent Runner** | Python + LangGraph container (WatsonX / `langchain-ibm`); `bash` + `http_check` embedded tools; `AGENTS.md` persona injection; `SKILL.md` declarative skill injection; MCP multi-server client (`MultiServerMCPClient`) |
| **Control Plane** | FastAPI service; Kubernetes Provisioner (Namespace + Pod + ConfigMap + ResourceQuota + NetworkPolicy per agent); TTL Garbage Collector; WebSocket chat proxy with multi-conversation support (`conversation_id`); auto-titling of conversations |
| **A2A** | Agent Card (`/.well-known/agent.json`) published at runner boot; push handshake (`POST /agents/{id}/handshake`) + pull fallback; A2A task lifecycle (`submitted → working → completed / failed`); task delegation between agents (`POST /agents/{id}/delegate`) |
| **Automations** | Background triggers in the runner: Cron, Timer, Webhook |
| **CLI** | `golem cp *` — multi-context control plane management; `golem agent create/list/delete/status`; `golem agent tasks` / `golem agent task-send`; `golem chat`; `golem conv *` conversation management |
| **Security** | K8s RBAC (least-privilege ClusterRole); per-sandbox NetworkPolicy (default-deny egress); ResourceQuota per agent; secrets injected via `envFrom` |

---

## MVP 2 — Multi-Provider & Personal Assistant Mode  `September 2026`

**Goal:** Remove the WatsonX lock-in and enable Golem as a lightweight personal assistant with no cloud dependency.

**Wow demos unlocked:**
- Deploy a Golem agent on **Ollama** running locally — zero IBM Cloud, zero API key, works offline.
- Run `golem agent create` on your Mac — no Minikube, no Docker, just Python processes.

**Estimated effort: ~17 hours**

| Area | Est. hours |
|---|:---:|
| Library extraction (`golem-agent-sdk` + `golem-framework`) | 8h |
| LLM Gateway — WatsonX formalisation | 2h |
| LLM Gateway — OpenAI-compatible protocol | 3h |
| LLM Gateway — Ollama native | 2h |
| `ProcessProvisioner` | 2h |

### Multi-Provider, Multi-Protocol, Multi-Model

- [ ] Extract `golem-agent-sdk` — A2A lifecycle, Agent Card, handshake; **no LLM dependency**; importable by non-LLM agents
- [ ] Extract `golem-framework` — LangGraph agentic loop + LLM Gateway abstraction; `golem-runner` becomes a thin entrypoint that imports both
- [ ] **LLM Gateway — WatsonX** formalised as a `golem-framework` backend (`provider=watsonx`, `protocol=watsonx`) — behaviour unchanged
- [ ] **LLM Gateway — OpenAI-compatible** (`protocol=openai`) — any OpenAI-compatible endpoint: public OpenAI, vLLM, LM Studio, Ollama `/v1`
- [ ] **LLM Gateway — Ollama native** (`provider=ollama`, `protocol=ollama`) — direct Ollama REST API
- [ ] `config.yaml` `llm.provider` + `llm.protocol` selects the gateway at runner boot; no rebuild required

### `ProcessProvisioner` — Personal Assistant Mode

*The lightest possible way to run Golem: no Docker, no Kubernetes, no containers — just Python.*

- [ ] `create_sandbox` — writes `config.yaml` + `AGENTS.md` + skills to `~/.golem/agents/<id>/`, launches the runner as a background subprocess (`uv run python main.py`) on a free port; returns `SandboxHandle(endpoint=http://localhost:<port>)`
- [ ] `delete_sandbox` — terminates the subprocess, removes `~/.golem/agents/<id>/`
- [ ] `get_status` — subprocess alive + `/health` responds → `RUNNING`; otherwise `FAILED`
- [ ] TTL GC unchanged — calls `delete_sandbox` when TTL expires
- [ ] `config.yaml`: `control-plane.provisioner: process`, `control-plane.runner_path: /path/to/golem-runner`

---

## MVP 3 — MCP Registry & Skill Registry  `October 2026`

**Goal:** Make MCP servers reusable across agents and introduce versioned skills from Git.

**Wow demos unlocked:**
- Register the Kubernetes MCP server once — deploy three different SRE agents that all use it without repeating a URI.
- `golem agent create --skill sre-diagnostics` — no file upload; skill resolved from a Git repo automatically.

**Estimated effort: ~14 hours**

| Area | Est. hours |
|---|:---:|
| MCP Registry | 6h |
| Skill Registry | 5h |
| CLI additions | 3h |

### MCP Registry

- [ ] MCP Registry in Control Plane — register named MCP servers; agents reference them by name instead of raw URI
- [ ] **Shared** mode — one pod in `golem-mcp-shared` namespace, reusable by all agents; **dedicated** mode — pod co-deployed in the agent namespace
- [ ] Support **external MCP servers** — servers running outside the cluster registered by name + URI
- [ ] CLI: `golem mcp add/list/remove`

### Skill Registry

- [ ] Skill Registry in Control Plane — register named Git repos as skill sources; resolve skill name → Git folder at agent creation time
- [ ] Runner: scan `/app/skills/*/SKILL.md` at boot; run `pip install -r requirements.txt` for skills with a `scripts/` directory
- [ ] CLI: `golem skill source add/list/remove/sync`, `golem skill list/show`

---

## MVP 4 — Resilience, Observability & Docker  `November 2026`

**Goal:** Survive restarts, make the platform observable, add Docker-based local deployment, and publish release artefacts.

**Wow demos unlocked:**
- Kill the Control Plane mid-conversation, restart — the conversation continues exactly where it stopped.
- `docker compose up` on a fresh machine — full Golem running in 2 minutes, no cluster.
- Open Langfuse, watch every LLM call traced live with token counts and latencies.

**Estimated effort: ~19 hours**

| Area | Est. hours |
|---|:---:|
| Resilience (Redis + PostgreSQL) | 6h |
| Observability (external Langfuse) | 3h |
| `DockerProvisioner` + Compose bundle | 4h |
| Docker Hub CI + Helm Chart | 4h |
| CLI `--reasoning` flag | 2h |

### Resilience — Do Not Lose State on Restart

- [ ] **LangGraph checkpointer on Redis** — persist graph state at every step; conversations survive pod restarts and TTL expiry
- [ ] Control Plane persists sandboxes, conversations, and tasks to **PostgreSQL**; survives Control Plane restarts
- [ ] **External Redis and PostgreSQL** supported — `redis.url` + `postgres.url` in `config.yaml`; absent → fall back to in-memory (MVP 1 behaviour unchanged)
- [ ] **Conversation rolling summary** — LangGraph summary node condenses history at a configurable token/message threshold; persisted to Redis; prevents context window overflow

### Observability — External Langfuse

- [ ] Instrument `golem-framework` LLM Gateway + agentic loop with Langfuse traces, generations, and spans
- [ ] Configure via `config.yaml` / `.env`: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`; absent → runner boots normally with no tracing
- [ ] Optional in-cluster Langfuse pod (`observability.enabled: true` in Helm values)

### `DockerProvisioner` — Personal Assistant Mode

- [ ] `create_sandbox` — `docker run -d` with a free host port; bind-mounts `~/.golem/agents/<id>/` into the container; returns `SandboxHandle(endpoint=http://localhost:<port>)`
- [ ] `delete_sandbox` — `docker rm -f`; `get_status` — `docker inspect`
- [ ] **`docker-compose` bundle** — single `docker-compose.yml` starts the control plane + pre-configured agents; `docker compose up` is the only command needed
- [ ] `config.yaml`: `control-plane.provisioner: docker`

### Release Infrastructure & CLI Polish

- [ ] **Container images on Docker Hub** — `golem-control-plane` and `golem-runner` published to `docker.io/` on every release tag via CI
- [ ] **Helm Chart** — `helm install golem golem/control-plane`; `values.yaml` exposes image tags, credentials, Redis/PostgreSQL URLs, Langfuse config
- [ ] **CLI `--reasoning` flag** — `golem chat --reasoning {verbose,quiet,compact}`; runner emits a separate `event: reasoning` SSE stream; default `quiet`

---

## MVP 5 — Programmability & Advanced Agents  `December 2026`

**Goal:** Let developers inject custom graph logic and unlock deeper reasoning agent types without rebuilding the runner image.

**Wow demos unlocked:**
- Upload a `pipeline.py`, deploy an agent with a completely custom LangGraph — no image rebuild.
- Ask a deep agent to plan a multi-step investigation; watch it decompose the task, run sub-goals, and return a synthesised report.

**Estimated effort: ~15 hours**

| Area | Est. hours |
|---|:---:|
| Graph Plugin system | 7h |
| ReAct + Deep agent loop types | 5h |
| CLI + docs | 3h |

### Programmability — Custom Graph Upload

- [ ] `POST /agents` accepts `-F "graph=@pipeline.py"` — Control Plane mounts it as a ConfigMap (`runner-graph`)
- [ ] Runner loads `build_graph()` from `/app/graph/pipeline.py` at boot; falls back to built-in ReAct loop if absent
- [ ] CLI: `golem agent create --graph pipeline.py`

### ReAct & Deep Agent Types

- [ ] `loop: react` in `config.yaml` — default loop formalised as a first-class named type
- [ ] `loop: deep` — multi-step planning loop: agent decomposes the task into sub-goals, executes each with tools, reflects, and synthesises a final answer
- [ ] Agent loop type selectable per-agent in `config.yaml`; no runner rebuild required

---

## MVP 6 — Multi-Tenancy, Cloud & Workspaces  `Q1 2027`

**Goal:** Open the platform to multiple users, connect to IBM Cloud, and introduce persistent project workspaces.

**Estimated effort: ~22 hours — split across two months if needed.**

### Multi-Tenancy

- [ ] Account domain model — `Account` entity with API key auth (`Authorization: Bearer <key>`); no JWT/OAuth at this stage
- [ ] Ownership enforcement on all agent-scoped endpoints; `GET /agents` returns only the caller's agents
- [ ] CLI: `golem account create/whoami`; API key stored per context in `~/.golem/config.yaml`

### IBM Cloud Support

- [ ] **IBM Cloud Kubernetes Service (IKS) provisioner** — deploy agents on IKS clusters; IBM Cloud IAM authentication for the Control Plane
- [ ] **IBM Secrets Manager integration** — replace K8s Secrets with IBM Secrets Manager via External Secrets Operator
- [ ] **IBM Cloud Object Storage (COS) backend** — optional persistent storage for agent workspaces and skill artefacts

### Multi-Context CLI (kubectl-style)

- [ ] Named contexts in `~/.golem/config.yaml` (name, URL, token, account); `golem context list/add/use/delete`; all commands resolve the active context automatically

### Sandbox Modes: Stateful & Shared

| Mode | Pod per user | TTL GC | Persistent storage | Multi-user |
|---|:---:|:---:|:---:|:---:|
| **`ephemeral`** *(MVP 1 — done)* | ✅ | optional | ❌ | ❌ |
| **`stateful`** *(this milestone)* | ✅ | ❌ | ✅ PVC | ❌ |
| **`shared`** *(this milestone)* | ❌ one pod, N users | ❌ | optional | ✅ |

- [ ] `mode: stateful` — PVC-backed pod (`/workspace`); TTL GC skips stateful sandboxes; `golem agent create --mode stateful`
- [ ] `mode: shared` — one pod, N users via `conversation_id`; requires multi-tenancy above

### Project Model (Claude Code-style Workspaces)

- [ ] `Project` entity (`id`, `name`, `owner_id`, `agent_id`) with its own `AGENTS.md` + skills + conversations
- [ ] Chat routing: `WS /chat/{agent_id}?project_id=<id>&conversation_id=<uuid>` — runner selects project-scoped identity and skills per turn
- [ ] CLI: `golem project create/list/delete`, `golem project upload --agents-md / --skill`, `golem project conv list/new/switch`

---

## Phase 3 — Ecosystem Expansion  `2027`

*Items picked up opportunistically — no fixed schedule.*

| Item | Description |
|---|---|
| **Skill Marketplace** | Versioned, signed, public/private catalogue of Git and OCI skill repositories; `golem skill search/install/publish`; per-skill virtualenv isolation |
| **MCP Marketplace** | Versioned, signed, public/private catalogue of MCP servers; `golem mcp search/install/publish` |
| **AutoGen backend** | `golem-framework` AutoGen loop — swap LangGraph without changing the runner interface |
| **CrewAI backend** | `golem-framework` CrewAI loop |
| **LLM Gateway — Anthropic** | `provider=anthropic`, `protocol=anthropic` |
| **LLM Gateway — Hugging Face TGI** | `provider=huggingface`, `protocol=openai` |
| **Kubernetes Operator** | `GolemAgent` CRD + Operator for GitOps-style agent management; coexists with REST API |
| **OpenShift adapter** | `OpenShiftProvisioner` — Project, Route, Security Context Constraints |
| **Knative serverless runners** | Scale-to-zero agent execution; event-driven activation |
| **Web UI** | React dashboard for agent lifecycle, A2A task monitoring, and conversation management |
| **Signed A2A Agent Cards** | Cryptographic signature verification in the Card Registry (A2A v1.0 signing spec) |
| **gVisor / Kata Containers** | Runtime isolation for dynamic code execution sandboxes |
| **Graph plugin code signing** | Sign `pipeline.py` at upload; runner verifies before `exec`; OPA policy validation |
