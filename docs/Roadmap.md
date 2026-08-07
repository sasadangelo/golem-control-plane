# Golem — Roadmap

## MVP — 4-Week Sprint  `June 2026`

The goal of the MVP is a fully working **Agent-as-a-Service platform** running on any Kubernetes cluster (IBM Cloud, AWS, GCP, or a local Kind cluster).

> Items marked **`[new]`** were added after the initial design review to close the two main gaps: agent cooperation and network isolation.

---

### Week 1 — Control Plane & K8s Provisioner  `August W2`

**Goal:** Automate sandbox infrastructure creation.

- [x] FastAPI skeleton: `POST /agents`, `GET /agents/{id}/status`, `DELETE /agents/{id}`, `GET /agents`
- [x] Python `kubernetes-client` integration
- [x] Create isolated Namespace + Pod per agent
- [x] Apply `ResourceQuota` (CPU/RAM limits)
- [x] **`[new]`** `NetworkPolicy`: allow HTTPS (443) + DNS (53) egress only — deny all else
- [x] **`[new]`** Agent Card Registry: fetch and store card when pod reaches `Running`
- [x] **`[new]`** TTL-based sandbox garbage collection
- [x] **`[new]`** `Provisioner.create_sandbox()` abstract interface (K8s impl only for now)
- [x] Local end-to-end test: Control Plane as local process → creates pods in Minikube ✅ pod Running in < 10 s
- [x] **`[new]`** Deploy Control Plane inside Minikube (`golem-system` namespace + ServiceAccount + RBAC) ✅

**Deliverable:** `POST /agents` creates a live, isolated sandbox pod in under 10 seconds. ✅

---

### Week 3 — Chat Router & Persistence  `August W3`

**Goal:** End-to-end streaming communication between user and agent, with full history.

- [ ] WebSocket endpoint: `WS /chat/{agent_id}`
- [ ] Single ClusterIP gateway proxy — no per-pod Ingress
- [ ] Token streaming passthrough from pod to client
- [ ] Message history stored in PostgreSQL
- [ ] Agent state persistence in Redis
- [ ] **`[new]`** A2A task lifecycle records (`submitted → working → completed / failed`)
- [ ] **`[new]`** Control Plane as A2A broker: `GET /agents/{id}/card`, peer handshake endpoint

**Deliverable:** `golem chat --agent <id>` streams responses live from the sandbox pod.

---

### Week 4 — Automations, A2A Delegation & CLI  `August W4`

**Goal:** Background tasks, agent cooperation, and a polished CLI.

- [ ] Background tasks in Agent Runner: Cron, Timer, Webhook triggers
- [ ] CLI in Python + Typer: `agent create`, `chat`, `agent list`
- [ ] Helm Chart for Control Plane deployment
- [ ] **`[new]`** A2A `SendMessage` delegation between agents (e.g. `Log-Analyzer` → `Report-Writer`)
- [ ] **`[new]`** Signed Agent Card validation in the Card Registry
- [ ] **`[new]`** CLI: `golem agent tasks --agent <id>` — show A2A task lifecycle

**Deliverable:** a multi-agent flow works end-to-end; platform deployable on any K8s cluster via Helm.

---

## Component × Week Delivery Matrix

| Component | W1 | W2 | W3 | W4 |
|---|:---:|:---:|:---:|:---:|
| Agent Runner (Docker + LangGraph) | ✅ | — | — | Cron |
| A2A Agent Card + inbound tasks **`[new]`** | ✅ | — | Broker | SendMsg |
| Control Plane (FastAPI) | — | ✅ | Chat WS | Helm |
| K8s Provisioner (Python k8s-client) | — | ✅ | — | — |
| NetworkPolicy + TTL GC **`[new]`** | — | ✅ | — | — |
| Persistence (PostgreSQL + Redis) | — | — | ✅ | — |
| A2A task lifecycle + broker **`[new]`** | — | — | ✅ | — |
| CLI (Python + Typer) | — | — | — | ✅ |

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
golem chat --agent log-analyzer-001
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

#### 2.4 — Programmability: inject custom logic without rebuilding

| Item | Repository | Description |
|---|---|---|
| **Graph Plugin system** | `golem-framework` | `loop/plugin.py` — loads `build_graph()` from `/app/graph/pipeline.py` at boot; `POST /agents` accepts optional `-F "graph=@pipeline.py"`; Control Plane creates a second ConfigMap `runner-graph`; falls back to built-in ReAct loop if no plugin supplied |

#### 2.5 — Multi-tenancy: open to other users

| Item | Repository | Description |
|---|---|---|
| Multi-tenant RBAC (lightweight) | `golem-control-plane` | Per-user API key scoped to a set of sandbox namespaces; no full OAuth required at this stage |

#### 2.6 — Infrastructure

| Item | Repository | Description |
|---|---|---|
| Stateful Sandbox | `golem-control-plane` | PVC-backed agent pod for persistent state across sessions |
| Vault / external secret store | `golem-control-plane` | Replace K8s Secret with External Secrets Operator |
| gVisor / Kata Containers | infra | Runtime isolation for dynamic code execution |
| Go CLI binary | `golem-cli` | Distributable without Python runtime |
| **Provisioner Stage 1** | `golem-control-plane` | `DockerComposeProvisioner` for single-machine dev; `OpenShiftProvisioner` extending `KubernetesProvisioner` |

---

### Phase 3 — Ecosystem Expansion

| Item | Repository | Description |
|---|---|---|
| `golem-framework` AutoGen backend | `golem-framework` | `loop/autogen.py` — swap LangGraph for AutoGen |
| `golem-framework` CrewAI backend | `golem-framework` | `loop/crewai.py` — swap LangGraph for CrewAI |
| **LLM Gateway — OpenAI** | `golem-framework` | `provider=openai`, `protocol=openai` — public OpenAI API or any OpenAI-compat endpoint |
| Graph plugin code signing | `golem-control-plane` | Sign `pipeline.py` at upload time; runner verifies signature before `exec`; OPA policy validation |
| Multi-tenant isolation + RBAC | `golem-control-plane` | Per-tenant namespacing and API key scoping |
| **Provisioner Stage 2 — IAL** | `golem-control-plane` | Infrastructure Profiles (named bundles of backend + quota + NetworkPolicy) selectable via `PROVISIONER_BACKEND` |
| **Provisioner Stage 3 — Operator** | `golem-operator` | `GolemAgent` CRD + Kubernetes Operator for GitOps-style agent management (coexists with REST API) |
| Web UI for agent management | `golem-ui` | React dashboard for agent lifecycle and A2A task monitoring |
