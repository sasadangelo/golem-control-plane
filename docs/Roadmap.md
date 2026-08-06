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

| Phase | Item |
|---|---|
| Phase 2 | Extract `golem-agent-sdk` (A2A lifecycle + identity) as standalone internal library |
| Phase 2 | Extract `golem-framework` (LLM abstraction) as standalone internal library |
| Phase 2 | Stateful Sandbox: PVC-backed agent pod for persistent state across sessions (e.g. code-assistant working on a Git repo) |
| Phase 2 | Vault / external secret store integration |
| Phase 2 | gVisor / Kata Containers for dynamic code execution |
| Phase 2 | Go CLI binary (distributable without Python runtime) |
| Phase 2 | **Provisioner Stage 1**: `DockerComposeProvisioner` for single-machine dev; `OpenShiftProvisioner` extending `KubernetesProvisioner` (Project + Route + SCC delta) |
| Phase 3 | `golem-framework` AutoGen backend |
| Phase 3 | `golem-framework` CrewAI backend |
| Phase 3 | Multi-tenant isolation and RBAC |
| Phase 3 | **Provisioner Stage 2 — IAL**: Infrastructure Profiles (named bundles of backend + quota + NetworkPolicy) selectable via `PROVISIONER_BACKEND` env var |
| Phase 3 | **Provisioner Stage 3 — Operator**: `GolemAgent` CRD + Kubernetes Operator for GitOps-style agent management (coexists with REST API) |
| Phase 3 | Web UI for agent management |
