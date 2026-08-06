# Golem Runner — Agent Runner

The Golem Runner is the **atomic execution unit** of the Golem platform.
It is a single, generic Docker image that can be configured entirely at runtime via environment variables — no rebuild required.

See also: [Architecture](Architecture.md) · [Roadmap](Roadmap.md)

---

## Purpose

Each agent sandbox in Golem runs exactly one Agent Runner container.
The same image becomes a diagnostics agent, a code-writing assistant, or any other specialised agent simply by changing two environment variables.

---

## Directory Layout

```
src/golem-runner/
├── __init__.py
├── main.py           # FastAPI server — /chat and /health endpoints
├── agent.py          # LangGraph dynamic graph, built from env vars at startup
├── tools/
│   ├── __init__.py
│   ├── system_tools.py   # Skill: execute_bash_command
│   └── http_tools.py     # Skill: http_health_check
├── Dockerfile            # uv-based image, python:3.12-slim
├── pyproject.toml        # uv project dependencies
└── .env.example          # Template for local runs
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `WATSONX_API_KEY` | ✅ | — | IBM Cloud API key |
| `WATSONX_URL` | ✅ | `https://us-south.ml.cloud.ibm.com` | WatsonX endpoint URL |
| `WATSONX_PROJECT_ID` | ✅ | — | WatsonX project ID |
| `WATSONX_MODEL_ID` | | `openai/gpt-oss-120b` | Model identifier |
| `SYSTEM_PROMPT` | | `"You are a helpful generic automation agent."` | Agent persona and instructions |
| `ENABLED_SKILLS` | | `""` (no tools) | Comma-separated skill IDs to activate (see table below) |

### Available Skills

| Skill ID | Function | Description |
|---|---|---|
| `bash` | `execute_bash_command` | Runs a shell command inside the container; returns stdout/stderr |
| `http_check` | `http_health_check` | HTTP GET to a URL; returns status code and first 200 chars of body |

---

## HTTP API

### `POST /chat`

Send a message to the agent and receive a reply.

**Request**
```json
{ "message": "Check if https://google.com is reachable" }
```

**Response**
```json
{ "reply": "The site is reachable. Status Code: 200 ..." }
```

### `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

---

## Local Development with Docker

### 1. Build the image

```bash
docker build -t golem-runner:v1 src/golem-runner/
```

### 2. Run a diagnostics agent

```bash
docker run -d --name agent-test-1 \
  -p 8000:8000 \
  -e WATSONX_API_KEY="your-ibm-cloud-api-key" \
  -e WATSONX_URL="https://us-south.ml.cloud.ibm.com" \
  -e WATSONX_PROJECT_ID="your-watsonx-project-id" \
  -e WATSONX_MODEL_ID="openai/gpt-oss-120b" \
  -e SYSTEM_PROMPT="You are a network diagnostics agent. Use your tools to verify and resolve issues." \
  -e ENABLED_SKILLS="bash,http_check" \
  golem-runner:v1
```

### 3. Test the agent

**Generic response:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Who are you and what can you do?"}'
```

**HTTP health check tool:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Check if https://google.com is reachable"}'
```

**Bash tool:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many files are in the current directory and what is the container IP?"}'
```

### 4. Cleanup

```bash
docker stop agent-test-1 && docker rm agent-test-1
```

---

## Extending the Skill Catalogue

1. Add a new `@tool`-decorated function in `tools/` (e.g. `tools/db_tools.py`).
2. Register it in the `TOOL_REGISTRY` dict in [`agent.py`](../src/golem-runner/agent.py).
3. Pass its key in `ENABLED_SKILLS` at runtime.

No code changes are needed in `main.py` or the Dockerfile.

---

## Architecture Context

In the full Golem platform the Agent Runner pod is spawned and configured by the **K8s Provisioner** (Week 2).
The Control Plane injects `SYSTEM_PROMPT`, `ENABLED_SKILLS`, and `AGENT_ID` as Kubernetes Secret / ConfigMap values and enforces egress-only NetworkPolicy rules around the pod.

Full design: [Architecture.md](Architecture.md)
