# Golem Control Plane

The Control Plane is the **central brain** of the Golem platform.
It exposes the REST API, provisions agent sandboxes on Kubernetes, and maintains the A2A Agent Card Registry.

See also: [Architecture](Architecture.md) · [Golem Runner](GolemRunner.md) · [Roadmap](Roadmap.md)

---

## Directory Layout

```
src/golem-control-plane/
├── interfaces/api/app.py          # FastAPI app — REST endpoints
├── interfaces/api/schemas.py      # Pydantic request/response schemas
├── domain/models.py               # AgentSpec, SandboxHandle, SandboxStatus
├── domain/ports/provisioner.py    # Abstract Provisioner interface (ABC)
├── infrastructure/adapters/
│   ├── k8s_provisioner.py         # Kubernetes implementation
│   └── card_registry.py           # In-memory A2A Agent Card Registry (MVP)
├── core/config.py                 # Settings loaded from config.yaml
├── core/log.py                    # Structured logging (loguru)
├── config.yaml                    # Control Plane configuration
├── Dockerfile                     # uv-based image, python:3.12-slim, port 9000
├── pyproject.toml                 # uv project dependencies
└── .env.example                   # Template for local runs
```

---

## REST API

| Method | Path | Description |
|---|---|---|
| `POST` | `/agents` | Provision a new agent sandbox |
| `GET` | `/agents` | List all known sandboxes |
| `GET` | `/agents/{id}/status` | Get sandbox status + Agent Card |
| `DELETE` | `/agents/{id}` | Tear down sandbox |
| `GET` | `/agents/{id}/card` | Return A2A Agent Card (peer discovery) |
| `POST` | `/agents/{id}/handshake` | Runner pushes its Agent Card at startup (A2A broker registration) |
| `WS` | `/chat/{id}` | Bidirectional streaming chat proxy to the runner pod |
| `GET` | `/health` | Liveness probe |

### `POST /agents`

Accepts **`multipart/form-data`** (not JSON).

| Field | Type | Required | Default | Description |
|---|---|:---:|---|---|
| `config` | file | ✅ | — | Runner `config.yaml` uploaded as a file |
| `ttl_seconds` | int | | `3600` | Sandbox idle TTL before garbage collection |

**Example runner `config.yaml`**
```yaml
agent:
  name: log-analyzer
  system_prompt: "You are a log analysis agent."

llm:
  provider: watsonx
  model: openai/gpt-oss-120b

skills:
  - id: bash
  - id: http_check
```

**Response `201`**
```json
{
  "agent_id": "golem-agent-3f2a1b4c",
  "namespace": "golem-agent-3f2a1b4c",
  "status": "pending"
}
```

### `POST /agents/{id}/handshake`

Called by the **runner pod at startup** to register its Agent Card with the Control Plane broker
(push model).  After a successful handshake, the card is immediately available via
`GET /agents/{id}/card` — without waiting for a polling cycle.

**Request body**
```json
{
  "card": {
    "id": "golem-agent-3f2a1b4c",
    "name": "log-analyzer",
    "description": "Scans application logs for HTTP 500 errors.",
    "version": "0.1.0",
    "endpoint": "http://golem-agent-3f2a1b4c.golem-agent-3f2a1b4c.svc.cluster.local:8000",
    "capabilities": { "streaming": true, "pushNotifications": false },
    "skills": [{ "id": "bash", "name": "bash" }]
  }
}
```

**Response `200`**
```json
{ "registered": true, "agent_id": "golem-agent-3f2a1b4c" }
```

**Error `404`** — sandbox not found (the agent must be created via `POST /agents` first).

---

### Agent Card registration — push vs pull

The Control Plane maintains an in-memory **Agent Card Registry**.
Cards can enter the registry via two complementary paths:

| Path | Initiator | When | Notes |
|---|---|---|---|
| **Push (handshake)** | Runner pod | At pod startup | Immediate; runner calls `POST /agents/{id}/handshake` |
| **Pull (polling)** | Control Plane | On first `GET /agents/{id}/status` when pod is `RUNNING` | Fallback if runner does not call handshake |

---

### `GET /agents/{id}/status`

**Response**
```json
{
  "agent_id": "golem-agent-3f2a1b4c",
  "status": "running",
  "agent_card": {
    "id": "golem-agent-3f2a1b4c",
    "name": "log-analyzer",
    "skills": [{"id": "bash"}, {"id": "http_check"}]
  }
}
```

### `WS /chat/{id}`

Proxy WebSocket that forwards the session to the runner pod's `WS /ws/chat` endpoint.
The agent must be in `running` state — if not, the connection is closed immediately with a reason code.

**Protocol** (same as runner contract):

| Direction | Format | Content |
|---|---|---|
| client → Control Plane | text UTF-8 | user message |
| Control Plane → client | text UTF-8 | one LLM token |
| Control Plane → client | text `[DONE]` | end-of-response sentinel |
| Control Plane → client | text `[ERROR] …` | error from the runner loop |

**Close codes:**

| Code | Reason |
|---|---|
| `4404` | Agent not found |
| `4503` | Agent not in `running` state |
| `1011` | Unexpected proxy error |

---

## Configuration

### Secret (`.env`)

| Variable | Required | Description |
|---|:---:|---|
| `WATSONX_API_KEY` | ✅ | IBM Cloud API key — the only env var injected into every agent pod |

### Non-secret (`config.yaml`)

All other settings live in [`src/golem-control-plane/config.yaml`](../src/golem-control-plane/config.yaml).
Key fields:

| Key | Default | Description |
|---|---|---|
| `control-plane.runner_image` | `localhost/golem-runner:v1` | Docker image used for agent pods |
| `control-plane.gc_interval` | `60` | TTL garbage-collector interval (seconds) |
| `llm.provider` | `watsonx` | LLM provider identifier |
| `llm.model` | `openai/gpt-oss-120b` | Model used by agents |
| `llm.url` | `https://us-south.ml.cloud.ibm.com` | WatsonX regional endpoint |
| `llm.project_id` | — | WatsonX project ID |

---

## What the Provisioner creates per agent

```
K8s Namespace: golem-agent-<id>
├── ResourceQuota   — CPU: 500m req / 1 limit · RAM: 512Mi req / 1Gi limit
├── NetworkPolicy   — default-deny egress (allows 443/TCP + 53/UDP for DNS)
├── ConfigMap: runner-config  — mounts the uploaded config.yaml at /app/config.yaml
└── Pod: golem-agent-<id>-runner
    ├── Image: golem-runner:v1
    ├── Port: 8000
    ├── LivenessProbe: GET /health
    ├── VolumeMount: /app/config.yaml  (from ConfigMap runner-config)
    └── Env: WATSONX_API_KEY
```

---

## Local Development (requires Minikube)

### Prerequisites

```bash
# install and start Minikube
brew install minikube
minikube start --driver=docker --cpus=4 --memory=4096

# load the runner image into Minikube (no registry needed)
docker build -t golem-runner:v1 src/golem-runner/
minikube image load golem-runner:v1
```

### Run the Control Plane locally

```bash
cd src/golem-control-plane

# install dependencies
uv sync

# copy and fill credentials
cp .env.example .env

# start (kubeconfig is read from ~/.kube/config → Minikube)
uv run uvicorn app:app --reload --port 9000
```

### Test the full flow

```bash
# 1. create an agent (multipart upload of config.yaml)
curl -s -X POST http://localhost:9000/agents \
  -F "config=@/path/to/runner-config.yaml" \
  -F "ttl_seconds=3600" | python3 -m json.tool

# 2. poll status until running (Agent Card appears when pod is Ready)
curl -s http://localhost:9000/agents/<agent_id>/status | python3 -m json.tool

# 3. list all agents
curl -s http://localhost:9000/agents | python3 -m json.tool

# 4. stream a chat session (requires wscat: npm i -g wscat)
wscat -c ws://localhost:9000/chat/<agent_id>
# digita il tuo messaggio e ricevi i token in streaming, poi [DONE]

# 5. delete the agent
curl -s -X DELETE http://localhost:9000/agents/<agent_id>
```

---

## Architecture Context

The Control Plane is the only component **exposed outside the cluster**.
All agent pods run in isolated Namespaces with default-deny egress NetworkPolicy.
The Agent Card Registry here is in-memory (MVP); it will be backed by PostgreSQL in Week 3.

Full design: [Architecture.md](Architecture.md)
