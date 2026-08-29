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

**Goal:** Make MCP servers reusable across agents and introduce versioned skills from Git. Introduce a richer `config.yaml` as the single manifest for an agent.

**Wow demos unlocked:**
- Register the Kubernetes MCP server once — deploy three different SRE agents that all use it without repeating a URI.
- `golem agent create --skill sre-diagnostics` — no file upload; skill resolved from a Git repo automatically.
- One `config.yaml` file fully describes an agent — identity, skills, MCP servers, triggers — no separate uploads needed.

**Estimated effort: ~16 hours**

| Area | Est. hours |
|---|:---:|
| MCP Registry | 6h |
| Skill Registry | 5h |
| Rich `config.yaml` manifest | 2h |
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

### Rich `config.yaml` — Agent Manifest

*`config.yaml` becomes the single source of truth for an agent. No more separate multipart uploads.*

- [ ] `agent.identity` field — path to `AGENTS.md` relative to `config.yaml`; replaces inline `system_prompt` (backward-compatible: `system_prompt` still accepted if `identity` is absent)
- [ ] `agent.skills` as a structured list — built-in names (`bash`, `http_check`), local paths (`path: ./skills/k8s.md`), and registry references (`source: acme/sre@v1.2`); replaces flat `enabled_skills` string (backward-compatible)
- [ ] `agent.mcp` entries accept both raw `url:` (existing) and named registry reference `name:` (new); Control Plane resolves names to URIs at provision time
- [ ] Control Plane: when `POST /agents` receives only `config.yaml`, resolve `identity` and `skills` paths relative to the uploaded file; no `agents_md` or `skills` multipart fields required
- [ ] CLI: `golem agent create --config agent/config.yaml` resolves and uploads all referenced files automatically

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

**Goal:** Let developers inject custom graph logic, lightweight hooks, and unlock deeper reasoning agent types without rebuilding the runner image.

**Wow demos unlocked:**
- Upload a `pipeline.py`, deploy an agent with a completely custom LangGraph — no image rebuild.
- Ask a deep agent to plan a multi-step investigation; watch it decompose the task, run sub-goals, and return a synthesised report.
- Mount a `guardrail.py` hook — every LLM response is filtered before being returned, zero runner changes.

**Estimated effort: ~18 hours**

| Area | Est. hours |
|---|:---:|
| Graph Plugin system | 7h |
| ReAct + Deep agent loop types | 5h |
| Graph Hooks / Middleware | 3h |
| CLI + docs | 3h |

### Programmability — Custom Graph Upload

- [ ] `POST /agents` accepts `-F "graph=@pipeline.py"` — Control Plane mounts it as a ConfigMap (`runner-graph`)
- [ ] Runner loads `build_graph()` from `/app/graph/pipeline.py` at boot; falls back to built-in ReAct loop if absent
- [ ] CLI: `golem agent create --graph pipeline.py`

### ReAct & Deep Agent Types

- [ ] `loop: react` in `config.yaml` — default loop formalised as a first-class named type
- [ ] `loop: deep` — multi-step planning loop: agent decomposes the task into sub-goals, executes each with tools, reflects, and synthesises a final answer
- [ ] Agent loop type selectable per-agent in `config.yaml`; no runner rebuild required

### Graph Hooks — Lightweight Runtime Extension

*Surgical extension points on the built-in ReAct loop. Add state, guardrails, or context injection without writing a full `pipeline.py`.*

- [ ] Runner exposes hook points in the LangGraph graph: `before_agent`, `after_agent`, `before_tools`, `after_tools`, `on_final_answer`
- [ ] Hook files (`hooks/*.py`) mounted via ConfigMap alongside skills; each file must define a function matching the hook point name and receiving/returning the agent state
- [ ] `config.yaml` `agent.hooks` list — paths to hook files; loaded and wired into the graph at runner boot; absent → no-op, existing behaviour unchanged
- [ ] CLI: `golem agent create --hook ./hooks/guardrail.py`; Control Plane mounts each hook file as a separate ConfigMap entry
- [ ] Hook custom state fields merged into the base `AgentState` TypedDict at boot; hooks can read and write custom fields across turns

---

## MVP 6 — Multi-Tenancy, Cloud & Workspaces  `Q1 2027`

**Goal:** Turn Golem into a personal assistant reachable from the messaging apps you already use — without adding new infrastructure components. The existing Control Plane acts as the channel gateway.

**Wow demos unlocked:**
- Send a Telegram message to your Golem agent — get a full LLM response back in the chat.
- Ask your Slack bot to run a Kubernetes diagnostic — the SRE agent replies in the thread.
- One agent, multiple channels, same conversation history.

**Estimated effort: ~16 hours**

| Area | Est. hours |
|---|:---:|
| Channel Adapter framework in Control Plane | 4h |
| Telegram adapter | 3h |
| Slack adapter | 3h |
| WhatsApp adapter (Business API) | 4h |
| CLI + docs | 2h |

### Channel Adapter Framework

*Channels are inbound webhooks + outbound API calls wired into the existing WebSocket proxy. No new components.*

- [ ] `POST /channels/{channel}/{agent_id}` endpoint family in Control Plane — receives webhook payloads from messaging platforms
- [ ] Channel Adapter interface: `parse_inbound(payload) → (text, user_id, chat_id)` + `send_outbound(chat_id, text, token)`
- [ ] Stable `conversation_id` derived from channel + `chat_id` — same user always resumes the same conversation
- [ ] Control Plane routes inbound message to the runner via the existing WebSocket proxy; collects the streamed response and calls `send_outbound`
- [ ] `config.yaml` `agent.channels` section — declares which channels are active and injects credentials from `env_secrets`

```yaml
# config.yaml example
agent:
  channels:
    - type: telegram
      token: "${TELEGRAM_BOT_TOKEN}"
    - type: slack
      token: "${SLACK_BOT_TOKEN}"
      signing_secret: "${SLACK_SIGNING_SECRET}"
    - type: whatsapp
      token: "${WHATSAPP_TOKEN}"
      phone_number_id: "${WHATSAPP_PHONE_NUMBER_ID}"
```

### Telegram Adapter

- [ ] Verify Telegram webhook signature; parse `Update.message.text` and `chat.id`
- [ ] Register webhook URL via Telegram Bot API at Control Plane startup when `channels.telegram` is configured
- [ ] Send response via `POST https://api.telegram.org/bot<token>/sendMessage`; split messages exceeding 4096 chars

### Slack Adapter

- [ ] Verify Slack request signature (`X-Slack-Signature`); handle `url_verification` challenge
- [ ] Parse `event.text` and `event.channel` from Events API payload; ignore bot messages to prevent loops
- [ ] Post response via `chat.postMessage` with `thread_ts` to reply in-thread

### WhatsApp Adapter

- [ ] Verify webhook with `hub.verify_token` challenge (Meta platform)
- [ ] Parse `messages[0].text.body` and `from` (sender phone number) from Cloud API payload
- [ ] Send response via `POST https://graph.facebook.com/v18.0/{phone_number_id}/messages`

### CLI

- [ ] `golem agent channels` — list active channel adapters for a running agent
- [ ] Docs: channel setup guide per adapter (bot token, webhook URL registration)

---

## MVP 7 — Messaging Channels  `Q2 2027`

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
