<p align="center">
  <img src="docs/img/golem-logo.png" alt="Golem" width="320"/>
</p>

<h1 align="center">Golem</h1>
<p align="center"><strong>Kubernetes-native self-provisioning agentic platform</strong></p>
<p align="center">
  Multi-cloud · Multi-provider · Multi-model · Multi-protocol
</p>

---

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

## Golem Control Plane

The **Golem Control Plane** is a FastAPI service that manages isolated AI agent sandboxes on Kubernetes.

For each agent it provisions:
- a dedicated **Namespace** (derived from the agent ID)
- a **Pod** running the agent runner image
- a **ConfigMap** containing `config.yaml`, optional `AGENTS.md` (identity/behaviour context), and `SKILL.md` files (declarative skills)
- a **ResourceQuota** (CPU and memory limits)
- a **NetworkPolicy** (HTTPS + DNS egress only for security isolation)
- environment variables and secrets injected from existing K8s secrets (`env_secrets`)

It also provides:
- an in-memory **A2A Card Registry** with automatic polling and push-based startup handshake (`POST /agents/{id}/handshake`)
- an **A2A Task Broker & Delegation** service (`/tasks` and `/delegate`)
- a **WebSocket Chat Proxy** with multi-session / multi-conversation support (`/chat/{agent_id}?conversation_id=...`) and auto-titling
- a background **TTL Garbage Collector** that automatically tears down expired agent sandboxes

---

## Documentation

| Document | Description |
|---|---|
| [Local Deployment](docs/LocalDeployment.md) | Step-by-step guide to run and develop Control Plane locally |
| [Minikube Deployment](docs/MinikubeDeployment.md) | Full Kubernetes deployment guide on Minikube (`golem-system`) |
| [API Reference](docs/APIReference.md) | Complete REST API & WebSocket reference with schemas and curl examples |
| [Architecture](docs/Architecture.md) | Components, protocols (MCP / A2A), security model, and end-to-end data flow |
| [Security](docs/Security.md) | K8s RBAC, sandbox isolation, secrets management, and hardening roadmap |
| [Roadmap](docs/Roadmap.md) | MVP sprint plan, delivery matrix, and post-MVP milestones |
| [Demos](docs/Demos.md) | Catalogue of 10 high-impact demos — what to show, to whom, and in what order |

---

## Features

### Delivered (MVP)

| Feature | Status |
|---|:---:|
| Provision an isolated K8s sandbox (Namespace + Pod + ResourceQuota + NetworkPolicy) per agent | ✅ |
| Kubernetes RBAC — dedicated ServiceAccount with least-privilege ClusterRole | ✅ |
| Runner configuration via multipart `config.yaml` injected into ConfigMap | ✅ |
| Agent identity (`AGENTS.md`) and declarative skills (`SKILL.md`) mounted via ConfigMap | ✅ |
| MCP multi-server client — static URIs declared in `config.yaml`, tools registered at runner boot | ✅ |
| Secret injection via `env_secrets` referencing K8s secrets | ✅ |
| A2A Agent Card (`/.well-known/agent.json`) published at runner boot | ✅ |
| A2A Card Registry — push handshake (`POST /agents/{id}/handshake`) + pull fallback | ✅ |
| A2A Task lifecycle broker (`submitted → working → completed / failed`) | ✅ |
| A2A Task Delegation between agents (`POST /agents/{id}/delegate`) | ✅ |
| Background automation triggers in runner: Cron, Timer, Webhook | ✅ |
| WebSocket chat proxy — bidirectional token streaming from runner pod to client | ✅ |
| Multi-conversation support (`conversation_id` per session) with auto-titling | ✅ |
| TTL-based garbage collector — optional per-agent TTL, sandboxes without TTL live until deleted | ✅ |
| Abstract `Provisioner` interface (Kubernetes + Mock implementations) | ✅ |
| Control Plane deployable inside Minikube (`golem-system` namespace) | ✅ |
| CLI: `golem cp *` — multi-context control plane management | ✅ |
| CLI: `golem agent create/list/delete/status` — full agent lifecycle | ✅ |
| CLI: `golem agent tasks` / `golem agent task-send` — A2A task submission and inspection | ✅ |
| CLI: `golem chat` — interactive streaming chat | ✅ |
| CLI: `golem conv *` — conversation management | ✅ |

---

## Project Layout

```
golem-control-plane/
├── src/golem-control-plane/           # Application source code
│   ├── interfaces/api/
│   │   ├── app.py                     # FastAPI app, endpoints, WebSocket proxy, TTL GC
│   │   └── schemas.py                 # Pydantic request / response models
│   ├── domain/
│   │   ├── models.py                  # AgentSpec, SandboxHandle, SandboxStatus, A2ATask, Conversation
│   │   └── ports/
│   │       └── provisioner.py         # Abstract Provisioner interface (ABC)
│   ├── infrastructure/
│   │   └── adapters/
│   │       ├── k8s_provisioner.py     # Kubernetes client implementation
│   │       ├── mock_provisioner.py    # In-memory mock provisioner for local smoke-testing
│   │       └── card_registry.py       # In-memory A2A Agent Card Registry
│   ├── core/
│   │   ├── config.py                  # Pydantic settings & config loader
│   │   └── log.py                     # Structured loguru logging
│   └── config.yaml                    # Control Plane default configuration
├── deploy/golem-control-plane/        # Kubernetes manifests
│   ├── namespace.yaml                 # Namespace: golem-system
│   ├── serviceaccount.yaml            # ServiceAccount: golem-control-plane
│   ├── clusterrole.yaml               # RBAC ClusterRole
│   ├── clusterrolebinding.yaml        # RBAC ClusterRoleBinding
│   ├── deployment.yaml                # Control Plane Deployment (port 9000)
│   ├── service.yaml                   # ClusterIP Service
│   └── secret.yaml.example            # WatsonX credentials secret template
├── minikube/                          # Minikube helper scripts
│   ├── check-minikube-network.sh      # Network diagnostic helper
│   ├── fix-minikube-network.sh        # Network routing fix helper
│   ├── load_images.sh                 # Load local image into Minikube
│   └── delete_images.sh               # Cleanup images from Minikube
├── tests/unit/                        # Unit and integration test suite
├── docs/                              # Technical documentation
├── app.sh                             # Start the server locally
├── build_images.sh                    # Build the container image with Podman/Docker
├── delete_images.sh                   # Remove local container images
├── deploy.sh                          # Deploy manifests to Minikube / K8s
├── Dockerfile                         # Multi-stage uv container build
└── pyproject.toml                     # Dependencies, ruff, pytest, mypy config
```

---

## Getting Started

Choose a deployment guide based on your target environment:

- 🚀 **[Local Deployment Guide](docs/LocalDeployment.md)** — Run the Control Plane standalone with Python and `uv` for development and testing.
- ☸️ **[Minikube Deployment Guide](docs/MinikubeDeployment.md)** — Deploy the full Kubernetes-native setup with container builds, RBAC, and Secret management inside Minikube.

---

## API Reference

The complete REST API and WebSocket reference with request/response schemas, payloads, and `curl` examples is available in:

👉 **[API Reference Guide](docs/APIReference.md)**

---

## License

This project is licensed under the MIT License. See [`LICENSE.md`](LICENSE.md) for details.
