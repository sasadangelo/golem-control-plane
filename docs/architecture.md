# Golem — Architecture

## Introduction

**Golem** is a self-provisioning, Kubernetes-native agentic platform designed to run and orchestrate autonomous AI agents securely and efficiently.

The vision for Golem is to become a truly **multi-cloud, multi-provider, multi-model, and multi-protocol** ecosystem:
- **Deployment targets**: Today Golem is Kubernetes-native. The roadmap includes support for local deployments using **Docker** or **Podman**, virtual machines (**VMs**), and serverless architectures with **Knative**.
- **Agent frameworks**: The platform is currently implemented in **Python** leveraging **LangChain** and **LangGraph**, with planned support for frameworks such as **CrewAI** and **AutoGen**.
- **Models and protocols**: At present, Golem supports **WatsonX** as the model provider and protocol, enabling access to all LLMs supported on the WatsonX platform. Additional providers (e.g. OpenAI, Anthropic, Ollama, vLLM) and protocols will follow.

---

## Components

Golem is composed of three core components:

1. **[Golem Control Plane](https://github.com/sasadangelo/golem-control-plane)** *(this repository)* — The central orchestration service that exposes the management REST API, provisions sandboxed execution environments, routes conversations, and manages A2A (Agent-to-Agent) card registration and task broker interactions.
2. **[Golem Runner](https://github.com/sasadangelo/golem-runner)** — A generic, containerized AI agent runtime with a configurable loop (LangGraph-based), supporting tool execution (MCP), skills (`SKILL.md`), agent identity (`AGENTS.md`), and automation triggers (Cron, Timer, Webhook).
3. **[Golem CLI](https://github.com/sasadangelo/golem-cli)** — The unified command-line tool to administer the platform, manage control plane contexts, deploy and inspect agents, interact via streaming chat, and submit/monitor A2A tasks.

---

## Overview

![Golem Architecture](img/architecture.svg)

*(The architectural diagram is also available in editable Draw.io / XML format at [`docs/img/architecture.drawio`](img/architecture.drawio)).*

---

## MVP 1 Architecture

### 1. User Layer

- **Golem CLI (`golem`)**: Command-line interface built in Python with Typer. It serves as the primary administration and interaction client:
  - Context management (`golem cp *` to manage multiple control planes).
  - Agent sandbox lifecycle (`golem agent create`, `list`, `status`, `delete`).
  - Interactive streaming chat (`golem chat --agent <id>`).
  - Conversation management (`golem conv list`, `new`, `delete`).
  - A2A task submission and inspection (`golem agent task-send`, `task-get`, `tasks`).

---

### 2. Control Plane `FastAPI · Python`

The **Golem Control Plane** is the central orchestrator and API gateway of the platform. It is the sole component directly exposed to clients outside the Kubernetes cluster.

| Module / Service | Responsibility |
|---|---|
| **REST & WebSocket API** | Exposes endpoints for agent lifecycle (`POST /agents`, `GET /agents`, `DELETE /agents/{id}`), conversations (`/conversations`), task submissions (`/tasks`), and task delegation (`POST /agents/{id}/delegate`). |
| **WebSocket Chat Proxy** | Single internal ClusterIP gateway (`WS /chat/{agent_id}?conversation_id=...`) that routes bi-directional token streaming directly to the agent's runner pod without per-pod Ingress. Auto-generates conversation titles on the first turn. |
| **A2A Card Registry & Broker** | Maintains an in-memory registry of Agent Cards. Supports push registration (`POST /agents/{id}/handshake` called by runner at boot) and pull fallback (`GET /.well-known/agent.json`). Serves peer discovery queries (`GET /agents/{id}/card`) and brokers task delegation. |
| **Kubernetes Provisioner** | Output adapter implementing the `Provisioner` interface. Translates an `AgentSpec` into a dedicated Kubernetes `Namespace`, `ConfigMap` (for `config.yaml`, `AGENTS.md`, `SKILL.md`), `Pod`, `ResourceQuota`, and `NetworkPolicy`. |
| **TTL Garbage Collector** | Background asynchronous loop that monitors active sandboxes and automatically tears down expired sandboxes and namespaces. |

---

### 3. Golem Runner Pod `K8s Namespace per Agent`

Each agent executes inside its own isolated Kubernetes namespace (`<namespace>`).

Inside the pod, the architecture is layered as follows:

```
┌─────────────────────────────────────────────────────────────┐
│                     Golem Runner Pod                        │
│                                                             │
│  ┌───────────────────────────────┐  ┌────────────────────┐  │
│  │     LangGraph Agentic Loop    │  │    config.yaml     │  │
│  │   (ReAct / Skills Execution)  │  │     AGENTS.md      │  │
│  ├───────────────────────────────┤  │     SKILL.md       │  │
│  │        golem-framework        │  │ (Mounted ConfigMap)│  │
│  │ (LLM Gateway: WatsonX Client) │  └────────────────────┘  │
│  ├───────────────────────────────┤                          │
│  │        golem-agent-sdk        │                          │
│  │ (Lifecycle, Gateway, Handshake│                          │
│  │  A2A Client/Server, Triggers) │                          │
│  └───────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

#### Layer Breakdown:

1. **`golem-agent-sdk` (Lowest Layer)**:
   - Framework-agnostic foundation library.
   - Manages runner lifecycle (startup handshake with Control Plane, health probes, graceful shutdown).
   - Serves internal HTTP gateway and WebSocket chat endpoint.
   - Provides A2A client/server protocol implementation and automation triggers (Cron, Timer, Webhook).
   - Generates and exposes the machine-readable `/.well-known/agent.json` card adhering to the A2A v1.0 standard.
2. **`golem-framework`**:
   - Abstraction over LLM providers, protocols, and models.
   - In MVP1, implements the WatsonX model provider and protocol client for Granite and other supported models.
3. **`LangGraph Agentic Loop`**:
   - Drives reasoning and tool execution using LangChain/LangGraph.
   - Reads behavioral identity from `AGENTS.md` and dynamically selects declarative procedural skills from `SKILL.md`.
4. **Mounted Configuration (`config.yaml`)**:
   - Injected via Kubernetes `ConfigMap` alongside `AGENTS.md` and `skills/*.md`.
   - Injects credentials securely from Kubernetes Secrets (`env_secrets` / `WATSONX_API_KEY`).

---

### 4. Cooperation Layer & Protocols

#### MCP (Model Context Protocol) — Vertical Tool Execution (`Agent → Tool`)
- Enables agents to execute functions and access tools (log readers, database query tools, bash execution, external APIs).
- Tools are declared in `config.yaml` and whitelisted in the sandbox `NetworkPolicy`.

#### A2A (Agent-to-Agent Protocol) — Horizontal Delegation (`Agent ↔ Agent`)
- Enables autonomous cooperation between agents.
- Task lifecycle: `submitted → working → completed / failed`.
- In MVP1, agents delegate tasks via the Control Plane broker (`POST /agents/{source_agent_id}/delegate`), which forwards the payload to the target agent's `POST /a2a/tasks/send`.

---

### 5. Security & Isolation Layer

| Control | Implementation |
|---|---|
| **Kubernetes RBAC** | Control Plane runs under a dedicated `ServiceAccount` bound to a least-privilege `ClusterRole`. Agent runner pods possess no Kubernetes API privileges. |
| **Network Isolation** | Each sandbox namespace applies a `NetworkPolicy` enforcing default-deny egress, allowing only HTTPS (443) and DNS (53/UDP). |
| **Resource Limits** | `ResourceQuota` applied per agent namespace restricts CPU and Memory consumption to prevent noisy-neighbor cluster exhaustion. |
| **Secrets Management** | Injected via Kubernetes Secrets at runtime (`envFrom` / `valueFrom`), never baked into container image layers. |
| **Automated GC** | TTL-based expiration deletes stale namespaces and pods automatically. |

---

## Control Plane Internal Architecture (Hexagonal / Ports & Adapters)

The Control Plane codebase is structured following the **Hexagonal Architecture** pattern (also known as *Ports & Adapters*), originally described by Alistair Cockburn in 2005. The central principle is the **Dependency Rule**: every source-code dependency points inward, toward the Domain. No inner layer ever imports from an outer one.

### Folder Structure

```
src/golem-control-plane/
│
├── domain/                              ← DOMAIN (innermost — zero external dependencies)
│   ├── models.py                        ← AgentSpec, SandboxHandle, SandboxStatus,
│   │                                       A2ATask, Conversation
│   └── ports/                           ← Abstract contracts (interfaces) owned by the Domain
│       ├── provisioner.py               ← Provisioner port (sandbox lifecycle)
│       ├── sandbox_repo.py              ← SandboxRepository port (sandbox persistence)
│       └── task_repo.py                 ← TaskRepository, ConversationRepository ports
│
├── application/                         ← APPLICATION (use cases — no framework, no I/O)
│   └── services/
│       ├── agent_service.py             ← create / delete / list / status / handshake / GC loop
│       ├── task_service.py              ← submit / list / get / update / delegate
│       ├── conversation_service.py      ← create / list / delete / auto-name
│       └── chat_service.py             ← WebSocket proxy, active connection tracking
│
├── infrastructure/                      ← INFRASTRUCTURE (driven adapters — implements ports)
│   └── adapters/
│       ├── k8s_provisioner.py           ← implements Provisioner via Kubernetes API
│       ├── mock_provisioner.py          ← implements Provisioner in-memory (tests / local smoke)
│       ├── card_registry.py             ← in-memory A2A Agent Card registry
│       └── in_memory_repos.py           ← implements SandboxRepository, TaskRepository,
│                                           ConversationRepository (replaced by PostgreSQL in Week 3)
│
├── interfaces/                          ← INTERFACES (driving adapters — HTTP / WebSocket)
│   └── api/
│       ├── app.py                       ← FastAPI bootstrap, dependency wiring, lifespan (~110 lines)
│       ├── schemas.py                   ← Pydantic request / response DTOs
│       └── routers/
│           ├── agent_router.py          ← POST/GET/DELETE /agents, /handshake, /card
│           ├── task_router.py           ← POST/GET/PATCH /tasks, /delegate
│           ├── conversation_router.py   ← POST/GET/DELETE /conversations
│           └── chat_router.py          ← WS /chat/{agent_id}
│
└── core/                                ← CROSS-CUTTING (shared utilities, no business logic)
    ├── config.py                        ← Pydantic Settings (config.yaml + .env)
    └── log.py                           ← Structured logging (Loguru)
```

### Layer Responsibilities

| Layer | Responsibility | Depends on |
|---|---|---|
| **Domain** | Pure business entities (`models.py`) and abstract port interfaces. Contains no framework code, no I/O, no infrastructure knowledge. | Nothing |
| **Application** | One service class per use-case group. Orchestrates domain objects through ports. Contains all business logic (validation, state transitions, GC policy, auto-naming). | Domain only |
| **Infrastructure** | Concrete implementations of domain ports. Each adapter knows one external system (Kubernetes, in-memory dict, PostgreSQL). | Domain ports |
| **Interfaces** | HTTP routing and WebSocket handling (FastAPI). Translates HTTP verbs + JSON into service calls, maps exceptions to HTTP status codes. Contains no business logic. | Application services |
| **Core** | Configuration and logging utilities. Imported by all layers. | Nothing |

### Dependency Rule in Practice

```
┌─────────────────────────────────────────────────────────────────┐
│  Interfaces / api                                               │
│  (FastAPI routers — HTTP glue only)                             │
│                        │ calls                                  │
│  ┌─────────────────────▼───────────────────────────────────┐   │
│  │  Application / services                                 │   │
│  │  (business logic, use cases, GC loop)                   │   │
│  │                     │ uses ports                        │   │
│  │  ┌──────────────────▼──────────────────────────────┐   │   │
│  │  │  Domain                                         │   │   │
│  │  │  models.py + ports/ (abstract interfaces)       │   │   │
│  │  └──────────────────▲──────────────────────────────┘   │   │
│  │                     │ implements                        │   │
│  └─────────────────────┼───────────────────────────────────┘   │
│                        │                                        │
│  Infrastructure / adapters                                      │
│  (K8s, in-memory repos, card registry)                          │
└─────────────────────────────────────────────────────────────────┘
```

All arrows point inward. The Domain is never aware of FastAPI, Kubernetes, or any storage technology. The Application layer is never aware of HTTP status codes or SQL. Swapping an adapter — for example replacing `InMemorySandboxRepository` with `PostgresSandboxRepository` — requires changing a single line in `app.py` and writing the new adapter class; no business logic is touched.

### Driving vs. Driven Ports

Hexagonal Architecture distinguishes two kinds of ports:

- **Driving ports** (left side): the outside world *calls* the application. In this codebase that is the HTTP/WebSocket API in `interfaces/api/`. A user or the Golem CLI initiates an action.
- **Driven ports** (right side): the application *calls* the outside world. In this codebase those are `Provisioner`, `SandboxRepository`, `TaskRepository`, and `ConversationRepository` — all defined in `domain/ports/` and implemented in `infrastructure/adapters/`.

The Domain owns the contracts for both sides. Neither the HTTP framework nor the storage technology has any influence on the shape of the domain model.

---

## Future Developments & Roadmap

The post-MVP1 evolution of Golem includes:

1. **User Interface**:
   - **Web UI**: Web-based conversational dashboard and orchestration workspace.
2. **Multi-Target Provisioning**:
   - Local standalone container execution via **Docker** and **Podman** (no Kubernetes required).
   - Virtual Machine (**VM**) runners.
   - Serverless scaling via **Knative**.
   - **Serverless architecture**: event-driven, scale-to-zero agent execution with no persistent infrastructure.
   - Red Hat **OpenShift** adapter (Project, Route, Security Context Constraints).
   - Kubernetes Operator with `GolemAgent` Custom Resource Definitions (CRDs).
3. **Multi-Framework Ecosystem**:
   - Support for **CrewAI**, **AutoGen**, and custom Graph Plugin loaders (`pipeline.py`).
4. **Multi-Provider & Multi-Protocol**:
   - Native clients for **Ollama**, **OpenAI**, **Anthropic**, **vLLM**, and **Hugging Face TGI**.
5. **Durable Persistence & Observability**:
   - PostgreSQL and Redis for durable message history, agent cards, and task persistence.
   - Integrated LLM observability and tracing via **Langfuse** sidecar deployment.
   - Cryptographically signed Agent Cards for zero-trust A2A verification.
