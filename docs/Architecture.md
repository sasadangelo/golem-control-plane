# Golem — Architecture

> **Component deep-dives:** [Golem Control Plane](GolemControlPlane.md) · [Security Model](Security.md) · [Control Plane Internal Architecture](#control-plane-internal-architecture-hexagonal)

Golem is a **Kubernetes-native Agent-as-a-Service platform**.  
It lets you create isolated AI agents on demand, chat with them in streaming, let them cooperate with each other, and run autonomous background tasks — all from a single CLI or web interface.

---

## Overview

![Golem Architecture](img/architecture.svg)

The platform is built from **four core components** plus two internal libraries (Phase 2), one cross-cutting LLM gateway layer, and one optional observability sidecar (Phase 2) — bound together by two cooperation protocols (MCP and A2A).

---

## Components

### 1. Control Plane  `FastAPI · Python · PostgreSQL · Redis`

The central brain of the platform. It is the only component exposed outside the cluster.

| Service | Responsibility |
|---|---|
| **REST / WebSocket API** | `POST /agents` to create an agent; `WS /chat/{agent_id}` to stream messages |
| **Chat Proxy** | Single internal ClusterIP gateway that forwards WebSocket traffic to the correct agent pod — no per-agent Ingress required |
| **A2A Card Registry** | Collects the Agent Card published by every pod at `/.well-known/agent.json`, verifies its signature, and answers peer-discovery queries ("who can do X?") |
| **K8s Provisioner** | Translates an agent creation request into a Kubernetes Namespace + Pod + ResourceQuota + NetworkPolicy + ConfigMap; also runs TTL-based garbage collection of idle sandboxes |
| **Persistence** | Stores message history, agent state, and A2A task lifecycle records in PostgreSQL (durable) and Redis (fast ephemeral state) |

---

### 2. Agent Sandbox  `K8s Namespace per agent`

Each agent lives in its own isolated Kubernetes Namespace.  
The sandbox contains a single **Agent Runner Pod** plus the security rules that protect both the agent and the rest of the cluster.

#### Agent Runner Pod

> Source repo: **`golem-runner`** (MVP: embedded monorepo; Phase 2: standalone repo)

A **single generic Docker image** parameterised entirely at runtime via a mounted `config.yaml` and a single environment variable (`WATSONX_API_KEY`).

The runner depends on **both** internal libraries (see §4):

```
golem-runner
├── uses golem-agent-sdk   → A2A identity, Agent Card, lifecycle heartbeat
└── uses golem-framework   → LangGraph loop + LLM Gateway
```

Two sandbox modes are supported:

| Mode | Storage | Lifecycle | Use case |
|---|---|---|---|
| **Ephemeral** *(MVP)* | No persistent volume | Created on `POST /agents`, deleted after TTL | Diagnostics, Q&A, one-shot automations |
| **Stateful** *(Phase 2)* | PVC mounted at `/workspace` | Lives until explicitly deleted | Code assistant, Git repo work, multi-session tasks |

---

### 3. Cooperation Layer

Two protocols handle agent interactions on orthogonal axes:

#### MCP — Model Context Protocol  `agent → tool (vertical)`

An agent uses MCP to call **tools and external resources**: read logs, query a database, call an API, access the filesystem.  
It is a function-call model (request → result).  
Tool endpoints are declared in the agent's `config.yaml` and whitelisted in the sandbox's NetworkPolicy.

#### A2A — Agent-to-Agent Protocol  `agent ↔ agent (horizontal)`

An agent uses A2A to **delegate tasks to peer agents** as autonomous actors.  
It is a task-delegation model with a full lifecycle (`submitted → working → completed / failed`) and structured artifact exchange.

- Initial peer discovery is brokered by the Control Plane's **A2A Card Registry**
- Once discovered, pods communicate directly via K8s ClusterIP Services
- Agent Cards are **signed** (A2A v1.0) to prevent a compromised sandbox from impersonating another agent

**Rule of thumb:** data or actions → MCP. Another agent's judgment or specialised capability → A2A.

---

### 4. CLI / Web Chat  `Python · Typer`

The user-facing surface. Implemented in Python (Typer) to share the same stack as the rest of the platform.

```
golem agent create --name "Log-Analyzer" --prompt "..." --skills read-logs
golem chat --agent log-analyzer-001
golem agent list
golem agent tasks --agent log-analyzer-001
```

---

## Internal Libraries — Phase 2

The Agent Runner today embeds all logic directly (MVP approach).  
As the platform matures, the runner is **split into three repositories**:

```
golem-runner          ← thin entrypoint; depends on the two libs below
golem-agent-sdk       ← A2A identity + platform lifecycle (no LLM calls)
golem-framework       ← LLM framework abstraction + LLM Gateway
```

### `golem-agent-sdk` — A2A lifecycle + platform identity

Everything related to the agent's identity and communication with the Golem platform.  
**Deliberately framework-agnostic** — it never makes LLM calls and can be imported by any runner regardless of the LLM backend (including non-LLM orchestrators or pure A2A proxies).

| Responsibility | Detail |
|---|---|
| **Agent Card** | Generates and serves `/.well-known/agent.json` (A2A v1.0) |
| **A2A client** | Delegates tasks to peer agents |
| **A2A server** | Receives inbound task delegations from peers |
| **Lifecycle** | Heartbeat, registration with Control Plane, graceful shutdown |
| **Config** | Standardised reading of Golem environment variables from `config.yaml` |

---

### `golem-framework` — LLM framework abstraction + LLM Gateway + Graph Plugin system

A portability layer with three responsibilities:

1. **Agentic loop abstraction** — hides the underlying framework (LangGraph, AutoGen, CrewAI…) behind a common interface so the runner never imports LangGraph directly
2. **LLM Gateway** — a provider/protocol/model router that maps a declarative config to the correct LLM client
3. **Graph Plugin system** — loads a custom LangGraph graph from a mounted Python file at runtime, with no image rebuild required

```
golem-framework
├── loop/
│   ├── base.py            ← abstract AgentLoop interface
│   ├── langgraph.py       ← built-in ReAct loop (default, no plugin needed)
│   ├── plugin.py          ← plugin loader: imports graph from /app/graph/pipeline.py
│   ├── autogen.py         ← Phase 3
│   └── crewai.py          ← Phase 3
└── llm_gateway/
    ├── base.py            ← abstract LLMClient interface
    ├── watsonx.py         ← provider=watsonx, protocol=watsonx
    ├── ollama_native.py   ← provider=ollama,  protocol=ollama
    └── ollama_openai.py   ← provider=ollama,  protocol=openai (Ollama OpenAI-compat API)
```

#### LLM Gateway — provider / protocol / model model

The gateway is configured by three orthogonal fields in `config.yaml`:

| Field | Meaning | Example values |
|---|---|---|
| `provider` | Who hosts the model | `watsonx`, `ollama`, `openai` |
| `protocol` | The wire format / API dialect used | `watsonx`, `ollama`, `openai` |
| `model` | The model identifier | `ibm/granite-3-8b-instruct`, `llama3.2`, `gpt-4o` |

The combination of `provider` + `protocol` selects the concrete backend:

| provider | protocol | Backend class | Notes |
|---|---|---|---|
| `watsonx` | `watsonx` | `WatsonxClient` | IBM Cloud, native WatsonX SDK |
| `ollama` | `ollama` | `OllamaNativeClient` | Local Ollama, native REST API |
| `ollama` | `openai` | `OllamaOpenAIClient` | Local Ollama via OpenAI-compat endpoint |
| `openai` | `openai` | `OpenAIClient` | OpenAI or any OpenAI-compat service |

**Why `protocol` is separate from `provider`:**  
Ollama exposes two APIs — its own native protocol and an OpenAI-compatible endpoint at `/v1`.  
Having separate fields lets you pick either without changing the `provider`.  
The same pattern extends to future providers that may expose multiple protocol variants.

**Why `llm-gateway` lives in `golem-framework` (not `golem-agent-sdk`):**

- The gateway makes LLM calls — that is framework-level work, not identity/lifecycle work
- `golem-agent-sdk` must remain importable by non-LLM agents (pure A2A proxies, orchestrators) — coupling it to an LLM SDK would break that contract
- Swapping the agentic backend (LangGraph → AutoGen) and swapping the LLM backend (WatsonX → Ollama) are both `golem-framework` concerns and should evolve together
- The runner imports both libraries independently; their separation keeps responsibilities clean:

```
golem-runner
    import golem_agent_sdk   → A2A, heartbeat, Agent Card   (no LLM dep)
    import golem_framework   → agentic loop + LLM Gateway + graph plugin loader
```

---

## Graph Plugin System  `Phase 2`

The built-in ReAct loop covers simple Q&A and tool-use scenarios. For complex cases — multi-source aggregation, structured Pydantic state, conditional branching, retry cycles — the runner supports injecting a **custom LangGraph graph at runtime** with no image rebuild.

### How it works

`POST /agents` accepts an optional second file upload alongside `config.yaml`:

```bash
curl -X POST http://localhost:9000/agents \
  -F "config=@config.yaml" \
  -F "graph=@pipeline.py"        # ← optional custom graph
```

The Control Plane provisioner creates **two ConfigMaps** in the sandbox namespace:

```
sandbox namespace (golem-agent-xxxxxxxx)
├── ConfigMap: runner-config     → mounted at /app/config.yaml     (already exists)
└── ConfigMap: runner-graph      → mounted at /app/graph/pipeline.py  (new, optional)
```

At boot, the runner checks for `/app/graph/pipeline.py`. If present, `golem-framework`'s plugin loader imports it and calls `build_graph()`. If absent, the built-in ReAct loop is used as fallback.

```python
# golem-framework/loop/plugin.py
import importlib.util
from pathlib import Path

PLUGIN_PATH = Path("/app/graph/pipeline.py")

def load_plugin_graph():
    if not PLUGIN_PATH.exists():
        return None                          # fallback to built-in ReAct
    spec = importlib.util.spec_from_file_location("graph_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # type: ignore[union-attr]
    return module.build_graph()              # convention: must expose build_graph()
```

### Plugin contract

A valid `pipeline.py` plugin must expose a single function:

```python
# pipeline.py — injected by the user at agent creation time
from langgraph.graph import StateGraph, START
from pydantic import BaseModel

class MyState(BaseModel):
    raw_data:  list[dict] = []
    result:    str        = ""

def build_graph() -> StateGraph:
    graph = StateGraph(MyState)
    graph.add_node("fetch",    fetch_data)
    graph.add_node("analyze",  analyze)
    graph.add_node("summarize", summarize)
    graph.add_edge(START,      "fetch")
    graph.add_edge("fetch",    "analyze")
    graph.add_edge("analyze",  "summarize")
    return graph.compile()
```

### What the plugin enables

| Scenario | Pattern |
|---|---|
| Multi-source data aggregation | Parallel `add_edge(START, node)` fan-out + fan-in to a merge node |
| Structured typed state | Pydantic `BaseModel` as `StateGraph` schema — validated at every step |
| Conditional branching | `add_conditional_edges` — runtime routing based on state values |
| Retry / refinement loops | Cycle edges back to earlier nodes until a condition is met |
| Human-in-the-loop | LangGraph `interrupt()` + `resume()` — pause graph, await external input |

### Security note

The plugin file is **code**, not configuration. It is mounted from a ConfigMap created by the Control Plane at provisioning time — it never comes directly from an unauthenticated source. Phase 3 hardening (code signing, OPA policy validation) is tracked in the Roadmap.

---

## Security & Isolation

> Full security model, RBAC design, and hardening roadmap: **[Security.md](Security.md)**

| Control | Detail |
|---|---|
| **K8s RBAC** | Control Plane runs as a dedicated `ServiceAccount` with a `ClusterRole` granting only the minimum verbs needed (Namespace + Pod + ResourceQuota + NetworkPolicy + ConfigMap). Agent Runner pods have no K8s identity. |
| **NetworkPolicy** | Per-sandbox allowlist: HTTPS (443) + DNS (53) egress only — all other traffic denied. |
| **ResourceQuota** | CPU and RAM hard limits per sandbox Namespace — a rogue agent cannot starve the cluster. |
| **Secrets** | K8s Secrets at MVP, never embedded in image layers. Migration path to Vault / External Secrets Operator planned for Phase 2. |
| **Sandbox GC** | TTL annotation on each pod — the Control Plane GC loop deletes idle sandboxes automatically. |
| **Runtime isolation** | gVisor / Kata Containers recommended for dynamic code execution (Phase 3). |

---

## Observability — Langfuse  `Phase 2 · standalone Docker image`

Golem's observability layer is built around **[Langfuse](https://langfuse.com/)** — an open-source LLM tracing and evaluation platform deployed as a separate Docker image inside the cluster.

### Deployment model

Langfuse runs as its own K8s `Deployment` in the `golem-system` namespace, exposed via a `ClusterIP` Service (no external Ingress).
It is completely optional: when `LANGFUSE_HOST` is absent from a runner's config, tracing is silently disabled.

```
golem-system namespace
├── golem-control-plane   (existing)
├── langfuse              (new — standalone image)
│   ├── Deployment        langfuse/langfuse:latest
│   ├── Service           ClusterIP :3000
│   └── PVC               PostgreSQL data (or external managed DB)
└── ...

Agent sandbox namespace (per agent)
└── runner pod
    └── golem-framework → LLM Gateway
            │  traces (HTTP/OTLP)
            ▼
        langfuse:3000  (ClusterIP, internal only)
```

### What gets traced

| Signal | Emitter | Langfuse object |
|---|---|---|
| LLM call (prompt + completion + tokens) | `golem-framework` LLM Gateway | `Generation` |
| Agentic loop iteration (reasoning step) | `golem-framework` loop backend | `Span` |
| Tool call (MCP invocation + result) | `golem-framework` loop backend | `Span` |
| A2A task delegation (SendMessage) | `golem-agent-sdk` A2A client | `Span` |
| Agent request lifecycle | Control Plane | `Trace` (root) |

### Instrumentation placement

Tracing is instrumented at the `golem-framework` boundary — specifically inside the LLM Gateway and the agentic loop abstraction.
This means **zero tracing code in `golem-runner`** and **zero tracing code in `golem-agent-sdk`**:

```
golem-runner  →  golem-framework (loop + LLM Gateway)  →  Langfuse SDK  →  langfuse:3000
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                 only place that knows about LLM calls
```

### NetworkPolicy implication

Runner pods need egress to the Langfuse ClusterIP. This is an **internal cluster address** (not the internet), so it is added as an explicit egress rule alongside the existing HTTPS/DNS allowlist:

```yaml
# added to sandbox NetworkPolicy when observability is enabled
- ports:
    - port: 3000
      protocol: TCP
  to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: golem-system
      podSelector:
        matchLabels:
          app: langfuse
```

### Configuration

Langfuse credentials are passed to runner pods via the `config.yaml` ConfigMap (non-secret values) and a K8s Secret (secret key):

```yaml
# config.yaml (non-secret)
observability:
  enabled: true
  host: "http://langfuse.golem-system.svc.cluster.local:3000"

# K8s Secret (secret values)
LANGFUSE_SECRET_KEY: sk-lf-...
LANGFUSE_PUBLIC_KEY: pk-lf-...
```

---

## Data Flow — End-to-End Example

User asks `Log-Analyzer` to analyse logs and produce a PDF report (delegated to `Report-Writer`):

```
User CLI
  → WS /chat/log-analyzer-001          (Control Plane WebSocket API)
    → Log-Analyzer Pod                 (golem-framework: LangGraph loop)
      → LLM Gateway → WatsonX          (golem-framework: llm_gateway/watsonx.py)
      → MCP: read-logs tool            (get raw log data)
      → A2A: SendMessage → Control Plane Card Registry
        → Report-Writer Pod            (A2A task: submitted → working)
          → LLM Gateway → Ollama       (golem-framework: llm_gateway/ollama_native.py)
          → MCP: pdf-generator tool
          ← artifact: report.pdf       (A2A task: completed)
      ← A2A artifact received
  ← streaming response + PDF link      (User CLI)
```

`Log-Analyzer`'s NetworkPolicy permits egress only to:
1. WatsonX endpoint (HTTPS/443)
2. The `read-logs` MCP server endpoint
3. `Report-Writer`'s ClusterIP Service

If `Log-Analyzer` is compromised, it cannot reach any other pod or the public internet beyond the allowed ports.

---

## Provisioner Abstraction

The K8s Provisioner is accessed through a `Provisioner.create_sandbox()` interface. The only implementation for MVP is Kubernetes, but the abstraction allows adding new backends without rewriting the Control Plane.

```python
class Provisioner(ABC):
    @abstractmethod
    def create_sandbox(self, agent: AgentSpec) -> SandboxHandle: ...

    @abstractmethod
    def delete_sandbox(self, handle: SandboxHandle) -> None: ...
```

The three evolution stages planned post-MVP:

### Stage 1 — Multi-backend Provisioner  `Phase 2`

Additional concrete implementations of the same `Provisioner` ABC, selectable via a `PROVISIONER_BACKEND` environment variable:

| Backend | Use case |
|---|---|
| `kubernetes` *(MVP)* | Any K8s cluster (Minikube, Kind, cloud-managed) |
| `docker-compose` | Single-machine development; no K8s required |
| `openshift` | Red Hat OpenShift (Project + Route + SCC delta) |

The `OpenShiftProvisioner` extends `KubernetesProvisioner` and overrides only the three OpenShift-specific resources. All other provisioning logic is inherited unchanged.

### Stage 2 — Infrastructure Abstraction Layer (IAL) with Profiles  `Phase 3`

The Control Plane gains a concept of **Infrastructure Profiles** — named bundles of backend + resource policy + network rules stored as ConfigMaps.

```
IAL Profiles
├── local-dev      → DockerComposeProvisioner, no quota, no NetworkPolicy
├── k8s-standard   → KubernetesProvisioner, 1 CPU / 512 MB, default-deny egress
└── openshift-prod → OpenShiftProvisioner, 2 CPU / 1 GB, SCC restricted
```

### Stage 3 — Operator Pattern  `Phase 3`

A Kubernetes Operator (`GolemAgent` CRD) replaces the REST `POST /agents` workflow for cloud-native environments.

```yaml
apiVersion: golem.io/v1alpha1
kind: GolemAgent
metadata:
  name: log-analyzer
spec:
  systemPrompt: "Scan application logs for HTTP 500 errors."
  enabledSkills: ["bash", "http_check"]
  ttlSeconds: 3600
  infraProfile: k8s-standard
```

The REST API and the Operator coexist: both drive the same `Provisioner` layer.

---

## Control Plane Internal Architecture (Hexagonal)

The Control Plane is organised following the **Hexagonal Architecture** (Ports & Adapters) pattern.
The domain is at the centre and has zero dependencies on frameworks, Kubernetes, or HTTP.
All external technology is pushed to the edges as interchangeable adapters.

```
src/golem-control-plane/
│
├── domain/                          ← CENTRE OF THE HEXAGON
│   ├── models.py                    ← AgentSpec, SandboxHandle, SandboxStatus (pure domain entities)
│   └── ports/
│       └── provisioner.py           ← Provisioner ABC (output port — abstract interface)
│
├── infrastructure/                  ← DRIVEN ADAPTERS (called by the domain)
│   └── adapters/
│       ├── k8s_provisioner.py       ← KubernetesProvisioner (implements Provisioner port)
│       └── card_registry.py         ← In-memory A2A Card Registry (HTTP fetch + dict store)
│
├── interfaces/                      ← DRIVING ADAPTERS (call the domain from the outside)
│   └── api/
│       ├── app.py                   ← FastAPI application factory + all HTTP endpoints
│       └── schemas.py               ← Pydantic request/response schemas (HTTP boundary DTOs)
│
└── core/                            ← CROSS-CUTTING (shared by all layers)
    ├── config.py                    ← Settings singleton (config.yaml + .env)
    └── log.py                       ← Loguru setup + LoggerManager
```

### Layer responsibilities

| Layer | Role | Depends on |
|---|---|---|
| **Domain** | Pure business logic, entities, abstract port interfaces | Nothing |
| **Infrastructure / Adapters** | Concrete implementations of output ports (K8s, HTTP) | Domain only |
| **Interfaces / API** | HTTP driving adapter — translates HTTP ↔ domain calls | Domain + Infrastructure |
| **Core** | Cross-cutting config and logging | Nothing (loaded at startup) |

### Ports & Adapters map

```
                    ┌──────────────────────────────────────────┐
                    │            DOMAIN (hexagon)              │
  ┌─────────────┐   │  ┌────────────────────────────────────┐  │   ┌──────────────────────┐
  │  HTTP       │──▶│  │  domain/models.py                  │  │──▶│  infrastructure/     │
  │  (FastAPI)  │   │  │  AgentSpec · SandboxHandle         │  │   │  adapters/           │
  │             │   │  │                                    │  │   │  k8s_provisioner.py  │
  │ interfaces/ │   │  │  domain/ports/provisioner.py       │  │   │  (Kubernetes)        │
  │ api/app.py  │   │  │  Provisioner ABC  ← output port    │  │   └──────────────────────┘
  │             │   │  └────────────────────────────────────┘  │
  └─────────────┘   │                                          │   ┌──────────────────────┐
  Driving Adapter   │                                          │──▶│  infrastructure/     │
  (input side)      │                                          │   │  adapters/           │
                    └──────────────────────────────────────────┘   │  card_registry.py    │
                                                                   │  (HTTP + in-memory)  │
                                                                   └──────────────────────┘
                                                                   Driven Adapters
                                                                   (output side)
```

### Key design benefit — the Provisioner Port

[`domain/ports/provisioner.py`](../src/golem-control-plane/domain/ports/provisioner.py) defines
the `Provisioner` ABC with three abstract methods: `create_sandbox()`, `delete_sandbox()`,
`get_status()`. The HTTP layer and the GC loop call only this interface — they are completely
unaware of Kubernetes.

This means new backends can be added without touching a single line of application logic:

| Backend class | Location | Use case |
|---|---|---|
| `KubernetesProvisioner` *(MVP)* | `infrastructure/adapters/k8s_provisioner.py` | Any K8s cluster |
| `DockerComposeProvisioner` *(Phase 3)* | `infrastructure/adapters/docker_provisioner.py` | Local dev, no K8s |
| `MockProvisioner` *(tests)* | injected via `conftest.py` | Unit tests |

### Dependency direction (always inward)

```
interfaces/api  →  domain  ←  infrastructure/adapters
                     ↑
                   core/
```

No arrow ever points outward from domain. Infrastructure depends on domain (it implements its
ports). Interfaces depend on domain (it calls its use cases). Domain depends on nothing.
