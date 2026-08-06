# Golem Control Plane

The Control Plane is the **central brain** of the Golem platform.
It exposes the REST API, provisions agent sandboxes on Kubernetes, and maintains the A2A Agent Card Registry.

See also: [Architecture](Architecture.md) · [Golem Runner](GolemRunner.md) · [Roadmap](Roadmap.md)

---

## Directory Layout

```
src/golem-control-plane/
├── main.py             # FastAPI app — REST endpoints
├── models.py           # AgentSpec, SandboxHandle, SandboxStatus
├── provisioner.py      # Abstract Provisioner interface (ABC)
├── k8s_provisioner.py  # Kubernetes implementation
├── card_registry.py    # In-memory A2A Agent Card Registry (MVP)
├── Dockerfile          # uv-based image, python:3.12-slim, port 9000
├── pyproject.toml      # uv project dependencies
└── .env.example        # Template for local runs
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
| `GET` | `/health` | Liveness probe |

### `POST /agents`

**Request**
```json
{
  "name": "log-analyzer",
  "system_prompt": "You are a log analysis agent.",
  "enabled_skills": ["bash", "http_check"],
  "ttl_seconds": 3600
}
```

**Response `201`**
```json
{
  "agent_id": "golem-agent-3f2a1b4c",
  "namespace": "golem-agent-3f2a1b4c",
  "status": "pending"
}
```

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

---

## Environment Variables

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `RUNNER_IMAGE` | | `golem-runner:v1` | Docker image used for agent pods |
| `WATSONX_API_KEY` | ✅ | — | Injected into every agent pod |
| `WATSONX_URL` | ✅ | `https://us-south.ml.cloud.ibm.com` | Injected into every agent pod |
| `WATSONX_PROJECT_ID` | ✅ | — | Injected into every agent pod |
| `WATSONX_MODEL_ID` | | `openai/gpt-oss-120b` | Injected into every agent pod |

---

## What the Provisioner creates per agent

```
K8s Namespace: golem-agent-<id>
├── ResourceQuota   — CPU: 500m req / 1 limit · RAM: 512Mi req / 1Gi limit
├── NetworkPolicy   — default-deny all egress
└── Pod: golem-agent-<id>-runner
    ├── Image: golem-runner:v1
    ├── Port: 8000
    ├── LivenessProbe: GET /health
    └── Env: AGENT_ID, SYSTEM_PROMPT, ENABLED_SKILLS, WATSONX_*
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
# 1. create an agent
curl -s -X POST http://localhost:9000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "diagnostics-agent",
    "system_prompt": "You are a network diagnostics agent.",
    "enabled_skills": ["bash", "http_check"]
  }' | python3 -m json.tool

# 2. poll status until running (Agent Card appears when pod is Ready)
curl -s http://localhost:9000/agents/<agent_id>/status | python3 -m json.tool

# 3. list all agents
curl -s http://localhost:9000/agents | python3 -m json.tool

# 4. delete the agent
curl -s -X DELETE http://localhost:9000/agents/<agent_id>
```

---

## Architecture Context

The Control Plane is the only component **exposed outside the cluster**.
All agent pods run in isolated Namespaces with default-deny egress NetworkPolicy.
The Agent Card Registry here is in-memory (MVP); it will be backed by PostgreSQL in Week 3.

Full design: [Architecture.md](Architecture.md)
