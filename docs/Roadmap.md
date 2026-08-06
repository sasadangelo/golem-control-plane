# Golem — Roadmap

## MVP — 4-Week Sprint  `June 2026`

The goal of the MVP is a fully working **Agent-as-a-Service platform** running on any Kubernetes cluster (IBM Cloud, AWS, GCP, or a local Kind cluster).

> Items marked **`[new]`** were added after the initial design review to close the two main gaps: agent cooperation and network isolation.

---

### Week 1 — Agent Runner & A2A Identity  `June W1`

**Goal:** Build and validate the generic agent container in isolation.

- [ ] Docker image in Python + LangGraph
- [ ] Read `SYSTEM_PROMPT`, `ENABLED_TOOLS`, `AGENT_ID` from environment variables
- [ ] Local Docker test: streaming chat response + MCP tool execution
- [ ] **`[new]`** Expose `/.well-known/agent.json` — A2A Agent Card endpoint
- [ ] **`[new]`** Integrate `a2a-sdk` for inbound peer task reception

**Deliverable:** a `docker run` command that starts a working, A2A-capable agent.

---

### Week 2 — Control Plane & K8s Provisioner  `June W2`

**Goal:** Automate sandbox infrastructure creation.

- [ ] FastAPI skeleton: `POST /agents`, `GET /agents/{id}/status`
- [ ] Python `kubernetes-client` integration (replaces client-go)
- [ ] Create isolated Namespace + Pod per agent
- [ ] Apply `ResourceQuota` (CPU/RAM limits)
- [ ] **`[new]`** `NetworkPolicy`: default-deny egress, whitelist MCP endpoints + A2A peer pods
- [ ] **`[new]`** Agent Card Registry: collect and verify cards when pod reaches `Ready`
- [ ] **`[new]`** TTL-based sandbox garbage collection
- [ ] **`[new]`** `Provisioner.create_sandbox()` abstract interface (K8s impl only for now)

**Deliverable:** `POST /agents` creates a live, isolated sandbox pod in under 10 seconds.

---

### Week 3 — Chat Router & Persistence  `June W3`

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

### Week 4 — Automations, A2A Delegation & CLI  `June W4`

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
| A2A Agent Card + `a2a-sdk` **`[new]`** | ✅ | — | Broker | SendMsg |
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

| Phase | Item |
|---|---|
| Phase 2 | Vault / external secret store integration |
| Phase 2 | gVisor / Kata Containers for dynamic code execution |
| Phase 2 | Go CLI binary (distributable without Python runtime) |
| Phase 3 | Multi-tenant isolation and RBAC |
| Phase 3 | Docker Compose `Provisioner` backend for single-machine development |
| Phase 3 | Web UI for agent management |
