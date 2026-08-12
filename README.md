<p align="center">
  <img src="docs/img/golem-logo.png" alt="Golem Control Plane" width="320"/>
</p>

<h1 align="center">Golem Control Plane</h1>
<p align="center"><strong>Kubernetes-native agent sandbox provisioning and A2A Card Registry</strong></p>
<p align="center">
  Provision isolated AI agents on demand · Track their lifecycle · Discover them via A2A Agent Cards
</p>

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/Architecture.md) | Components, protocols (MCP / A2A), security model, and end-to-end data flow |
| [Security](docs/Security.md) | K8s RBAC, sandbox isolation, secrets management, and hardening roadmap |
| [Golem Control Plane](docs/GolemControlPlane.md) | REST API reference, K8s Provisioner, A2A Card Registry |
| [Roadmap](docs/Roadmap.md) | MVP sprint plan, delivery matrix, and post-MVP milestones |

---

## Overview

The **Golem Control Plane** is a FastAPI service that manages isolated AI agent sandboxes on Kubernetes.

For each agent it provisions:
- a dedicated **Namespace**
- a **Pod** running the agent runner image
- a **ResourceQuota** (CPU/memory limits)
- a **NetworkPolicy** (HTTPS + DNS egress only)

It also maintains an in-memory **A2A Card Registry** that auto-fetches and exposes each agent's `/.well-known/agent.json` card once the pod is Running.

A background **TTL garbage collector** automatically tears down expired sandboxes.

---

## Features

| Feature | Status |
|---|:---:|
| Provision an isolated K8s sandbox (Namespace + Pod + ResourceQuota + NetworkPolicy) per agent | ✅ |
| Kubernetes RBAC — dedicated ServiceAccount with least-privilege ClusterRole | ✅ |
| A2A Agent Card Registry — auto-fetches `/.well-known/agent.json` once pod is Running | ✅ |
| TTL-based garbage collector — tears down expired sandboxes automatically | ✅ |
| WebSocket chat proxy — streams LLM tokens from runner pod to client | ✅ |
| Single in-memory conversation state per agent (one message history per agent) | ✅ |
| `config.yaml` upload via multipart — injects runner configuration as a K8s ConfigMap | ✅ |
| Control Plane deployable inside Minikube (`golem-system` namespace) | ✅ |
| REST API: `POST /agents`, `GET /agents`, `GET /agents/{id}/status`, `DELETE /agents/{id}`, `GET /agents/{id}/card` | ✅ |
| Abstract `Provisioner` interface (K8s + Mock implementations) | ✅ |
| Multi-conversation support (`conversation_id` per session) | 🔜 |
| Helm Chart for one-command deployment | 🔜 |
| A2A task lifecycle broker (`submitted → working → completed / failed`) | 🔜 |

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Dependency management |
| [Podman](https://podman.io/) | 4+ | Container builds |
| [Minikube](https://minikube.sigs.k8s.io/) | latest | Local K8s cluster |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | 1.28+ | Cluster management |

---

## Project Layout

```
golem-control-plane/
├── src/golem-control-plane/    # Application source
│   ├── interfaces/api/app.py   # FastAPI app, endpoints, TTL GC
│   ├── domain/models.py        # AgentSpec, SandboxHandle, SandboxStatus
│   ├── domain/ports/           # Abstract Provisioner interface
│   ├── infrastructure/         # K8s + Mock provisioner, Card Registry
│   └── core/                   # Config, logging
├── deploy/golem-control-plane/ # K8s manifests
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── clusterrole.yaml
│   ├── clusterrolebinding.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── secret.yaml.example
├── minikube/
│   └── load_images.sh          # Save image with Podman and load into Minikube
├── tests/unit/                 # Unit tests
├── docs/                       # Architecture, Security, Roadmap
├── app.sh                      # Start the server locally
├── build_images.sh             # Build the container image with Podman
├── deploy.sh                   # Deploy to Minikube / K8s
├── Dockerfile                  # Container image
└── pyproject.toml              # Dependencies, ruff, pytest config
```

---

## Local Development

### 1. Install dependencies

```bash
uv sync --extra dev
```

### 2. Run the test suite

```bash
uv run python -m pytest tests/unit/ -v
```

### 3. Start the server locally

```bash
./app.sh
```

Configuration is split between two files:

**`src/golem-control-plane/config.yaml`** — non-secret values, committed to the repo:

| Field | Default | Description |
|---|---|---|
| `control-plane.host` | `0.0.0.0` | Bind address |
| `control-plane.port` | `9000` | Bind port |
| `control-plane.workers` | `1` | Uvicorn worker count |
| `control-plane.gc_interval` | `60` | TTL GC polling interval (seconds) |
| `control-plane.runner_image` | `localhost/golem-runner:v1` | Agent runner image |
| `llm.provider` | `watsonx` | LLM provider identifier |
| `llm.protocol` | `watsonx` | LLM protocol identifier |
| `llm.model` | `openai/gpt-oss-120b` | Model identifier |
| `llm.project_id` | — | WatsonX project ID |
| `llm.url` | `https://us-south.ml.cloud.ibm.com` | WatsonX endpoint |

**`src/golem-control-plane/.env`** — secrets only, never committed (copy from `.env.example`):

| Variable | Description |
|---|---|
| `WATSONX_API_KEY` | IBM WatsonX API key |

### 4. Smoke test the local server

In a second terminal, while `./app.sh` is running:

```bash
# Health check — must return {"status": "ok"}
curl -s http://localhost:9000/health

# List agents — must return []
curl -s http://localhost:9000/agents

# Create an agent — will return HTTP 500 because there is no K8s cluster locally (expected)
curl -s -X POST http://localhost:9000/agents \
  -F "config=@/path/to/config.yaml" \
  -F "ttl_seconds=3600"
```

### 5. Run linters

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/golem-control-plane/
```

---

## Deploy on Minikube

### Step 1 — Start Minikube

```bash
minikube start --driver=podman --container-runtime=containerd
```

### Step 2 — Build and load the Control Plane image

```bash
./build_images.sh
./minikube/load_images.sh
```

### Step 3 — Create the WatsonX credentials secret

```bash
cp deploy/golem-control-plane/secret.yaml.example deploy/golem-control-plane/secret.yaml
# Edit secret.yaml and fill in your real credentials — never commit this file
```

### Step 4 — Deploy

```bash
./deploy.sh
```

`deploy.sh` applies all manifests in order and waits for the rollout to complete.

### Step 5 — Port-forward and smoke test

```bash
# Terminal 1 — keep open
kubectl -n golem-system port-forward svc/golem-control-plane 9000:9000

# Terminal 2 — smoke tests
curl -s http://localhost:9000/health
curl -s http://localhost:9000/agents
```

---

## API Quick Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/agents` | Provision a new agent sandbox |
| `GET` | `/agents` | List all known sandboxes |
| `GET` | `/agents/{id}/status` | Get sandbox status |
| `GET` | `/agents/{id}/card` | Get A2A Agent Card |
| `DELETE` | `/agents/{id}` | Tear down sandbox |

### Create an agent

`POST /agents` accepts `multipart/form-data` with:
- `config` — the runner `config.yaml` file (required)
- `ttl_seconds` — sandbox TTL in seconds (optional, default `3600`)

```bash
curl -s -X POST http://localhost:9000/agents \
  -F "config=@/path/to/config.yaml" \
  -F "ttl_seconds=3600" \
  | python3 -m json.tool
```

Use the returned `agent_id` to monitor the sandbox:

```bash
AGENT_ID=golem-agent-xxxxxxxx

# Watch the pod
kubectl -n ${AGENT_ID} get pods -w

# Verify the ConfigMap was created with the runner config
kubectl -n ${AGENT_ID} get configmap runner-config -o jsonpath='{.data.config\.yaml}'

# Poll status
curl -s http://localhost:9000/agents/${AGENT_ID}/status | python3 -m json.tool

# Chat with the agent (port-forward first)
kubectl -n ${AGENT_ID} port-forward pod/${AGENT_ID}-runner 8001:8000
curl -s http://localhost:8001/health

# Delete
curl -s -X DELETE http://localhost:9000/agents/${AGENT_ID}
```
