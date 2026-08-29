# Local Deployment Guide

This guide walks you through running the **Golem Control Plane** locally on your development workstation (standalone mode).

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Local runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Fast Python package and dependency manager |
| [curl](https://curl.se/) | any | HTTP testing and API interactions |

---

## Step 1 — Install Dependencies

Clone the repository and install dependencies using `uv`:

```bash
uv sync --extra dev
```

---

## Step 2 — Configure Settings and Secrets

Configuration is managed via two files:

### 1. `src/golem-control-plane/config.yaml` (Non-secret settings)
Default configuration values committed to version control:

```yaml
control-plane:
  host: "0.0.0.0"
  port: 9000
  workers: 1
  gc_interval: 60
  runner_image: "localhost/golem-runner:v1"

llm:
  provider: "watsonx"
  protocol: "watsonx"
  model: "openai/gpt-oss-120b"
  url: "https://us-south.ml.cloud.ibm.com"

test:
  provisioner: "mock" # Set to "mock" for local testing without a live Kubernetes cluster
```

### 2. `src/golem-control-plane/.env` (Secrets)
Create your local environment file from the template:

```bash
cp src/golem-control-plane/.env.example src/golem-control-plane/.env
```

Edit `src/golem-control-plane/.env` and set your credentials:
```bash
WATSONX_API_KEY="your-watsonx-api-key"  # pragma: allowlist secret
```

---

## Step 3 — Run Test Suite and Linters

Run the test suite to ensure the environment is working properly:

```bash
# Run unit tests
uv run python -m pytest tests/unit/ -v

# Run linters and type checkers
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/golem-control-plane/
```

---

## Step 4 — Start the Server

Start the FastAPI application with reload enabled:

```bash
./app.sh
```

The Control Plane will start listening on `http://localhost:9000`.

---

## Step 5 — Smoke Test Local Endpoints

Open a second terminal window to verify the server is responding:

```bash
# Liveness probe
curl -s http://localhost:9000/health
# Output: {"status":"ok"}

# List active agents
curl -s http://localhost:9000/agents
# Output: []
```
