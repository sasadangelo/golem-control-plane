<p align="center">
  <img src="docs/img/golem-logo.png" alt="Golem — Agentic Platform" width="320"/>
</p>

<h1 align="center">Golem</h1>
<p align="center"><strong>Kubernetes-native Agent-as-a-Service platform</strong></p>
<p align="center">
  Create isolated AI agents on demand · Chat with them in streaming · Let them cooperate · Run autonomous background tasks
</p>

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/Architecture.md) | Components, protocols (MCP / A2A), security model, and end-to-end data flow |
| [Roadmap](docs/Roadmap.md) | 4-week MVP sprint plan, delivery matrix, and post-MVP milestones |

---

## Quick Start

```bash
# Install dependencies
uv python install 3.14 && uv python pin 3.14
uv sync --group dev
```

```bash
# Run
uv run python -m golem.hello
```

```bash
# Test
uv run pytest tests
```

---

## Dev Tools

```bash
uv run ruff check src tests/
uv run ruff format src tests/
uv run mypy src
uv run bandit -r src
pre-commit run --all-files
```

---

## Overview

Golem is built on four core components:

1. **Control Plane** (FastAPI) — REST/WebSocket API, agent registry, chat proxy, K8s provisioner
2. **Agent Sandbox** — one isolated K8s Namespace per agent, with NetworkPolicy and ResourceQuota
3. **Agent Runner** — a single generic Docker image (LangGraph) configured at runtime via env vars
4. **CLI** — Python + Typer (`golem agent create`, `golem chat`, `golem agent tasks`)

Agents cooperate using **A2A** (Agent-to-Agent Protocol v1.0) for peer delegation and **MCP** (Model Context Protocol) for tool/resource access. See [docs/Architecture.md](docs/Architecture.md) for the full design.
