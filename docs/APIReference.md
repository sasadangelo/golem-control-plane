# Golem Control Plane — API Reference

This document provides complete documentation and usage examples for all REST and WebSocket endpoints exposed by the **Golem Control Plane** (port `9000`).

---

## Table of Contents

- [Overview](#overview)
- [System & Health Endpoints](#system--health-endpoints)
  - [`GET /health`](#get-health)
- [Agent Sandbox Lifecycle Endpoints](#agent-sandbox-lifecycle-endpoints)
  - [`POST /agents`](#post-agents)
  - [`GET /agents`](#get-agents)
  - [`GET /agents/{agent_id}/status`](#get-agentsagent_idstatus)
  - [`DELETE /agents/{agent_id}`](#delete-agentsagent_id)
- [A2A Card Registry & Handshake Endpoints](#a2a-card-registry--handshake-endpoints)
  - [`GET /agents/{agent_id}/card`](#get-agentsagent_idcard)
  - [`POST /agents/{agent_id}/handshake`](#post-agentsagent_idhandshake)
- [WebSocket Chat Proxy Endpoint](#websocket-chat-proxy-endpoint)
  - [`WS /chat/{agent_id}`](#ws-chatagent_id)
- [Conversation Management Endpoints](#conversation-management-endpoints)
  - [`POST /agents/{agent_id}/conversations`](#post-agentsagent_idconversations)
  - [`GET /agents/{agent_id}/conversations`](#get-agentsagent_idconversations)
  - [`DELETE /agents/{agent_id}/conversations/{conversation_id}`](#delete-agentsagent_idconversationsconversation_id)
- [A2A Task Management & Delegation Endpoints](#a2a-task-management--delegation-endpoints)
  - [`POST /agents/{agent_id}/tasks`](#post-agentsagent_idtasks)
  - [`GET /agents/{agent_id}/tasks`](#get-agentsagent_idtasks)
  - [`GET /agents/{agent_id}/tasks/{task_id}`](#get-agentsagent_idtaskstask_id)
  - [`PATCH /agents/{agent_id}/tasks/{task_id}`](#patch-agentsagent_idtaskstask_id)
  - [`POST /agents/{source_agent_id}/delegate`](#post-agentssource_agent_iddelegate)

---

## Overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check probe |
| `POST` | `/agents` | Provision a new sandboxed agent |
| `GET` | `/agents` | List all active agent sandboxes |
| `GET` | `/agents/{id}/status` | Get status and registered A2A Agent Card |
| `DELETE` | `/agents/{id}` | Tear down agent sandbox and clean up resources |
| `GET` | `/agents/{id}/card` | Retrieve A2A Agent Card for peer discovery |
| `POST` | `/agents/{id}/handshake` | Startup handshake from runner pushing Agent Card |
| `WS` | `/chat/{id}` | Bidirectional WebSocket chat streaming proxy |
| `POST` | `/agents/{id}/conversations` | Create a named conversation session |
| `GET` | `/agents/{id}/conversations` | List all conversations for an agent |
| `DELETE` | `/agents/{id}/conversations/{conv_id}` | Delete a conversation and close active WebSockets |
| `POST` | `/agents/{id}/tasks` | Submit an A2A task (fire-and-forget) |
| `GET` | `/agents/{id}/tasks` | List all A2A tasks for an agent |
| `GET` | `/agents/{id}/tasks/{task_id}` | Get status and result of a specific A2A task |
| `PATCH` | `/agents/{id}/tasks/{task_id}` | Update task status and result lifecycle |
| `POST` | `/agents/{source_agent_id}/delegate` | Broker A2A task delegation between agents |

---

## System & Health Endpoints

### `GET /health`
Liveness probe endpoint used by orchestrators (Kubernetes / load balancers) to confirm the service is alive.

**Response `200 OK`**
```json
{
  "status": "ok"
}
```

---

## Agent Sandbox Lifecycle Endpoints

### `POST /agents`
Provisions an isolated agent sandbox (Namespace, ConfigMap, Pod, ResourceQuota, NetworkPolicy).

Accepts `multipart/form-data`:
- `config` *(file, required)*: Runner `config.yaml` containing `agent.id`.
- `ttl_seconds` *(int, optional, default: 3600)*: Inactivity/lifecycle TTL in seconds.
- `agents_md` *(file, optional)*: Markdown file defining agent identity/behaviour context (`AGENTS.md`).
- `skills` *(files, optional)*: One or more `SKILL.md` declarative skill files.

**Example Request:**
```bash
curl -s -X POST http://localhost:9000/agents \
  -F "config=@config.yaml" \
  -F "agents_md=@AGENTS.md" \
  -F "skills=@skills/analyze-logs.md" \
  -F "ttl_seconds=3600"
```

**Response `201 Created`**
```json
{
  "agent_id": "log-analyzer-01",
  "namespace": "log-analyzer-01",
  "status": "pending"
}
```

---

### `GET /agents`
Returns a list of all known agent sandboxes with their live status.

**Example Request:**
```bash
curl -s http://localhost:9000/agents
```

**Response `200 OK`**
```json
[
  {
    "agent_id": "log-analyzer-01",
    "namespace": "log-analyzer-01",
    "status": "running",
    "agent_card": {
      "id": "log-analyzer-01",
      "name": "log-analyzer",
      "skills": [{"id": "analyze-logs"}]
    }
  }
]
```

---

### `GET /agents/{agent_id}/status`
Returns the status of a specific agent sandbox. If the pod has reached `RUNNING` status, automatically fetches and registers its A2A Agent Card.

**Example Request:**
```bash
curl -s http://localhost:9000/agents/log-analyzer-01/status
```

**Response `200 OK`**
```json
{
  "agent_id": "log-analyzer-01",
  "namespace": "log-analyzer-01",
  "status": "running",
  "agent_card": {
    "id": "log-analyzer-01",
    "name": "log-analyzer",
    "skills": [{"id": "analyze-logs"}]
  }
}
```

---

### `DELETE /agents/{agent_id}`
Tears down the agent sandbox, deletes all associated Kubernetes resources (Namespace, Pod, ConfigMap, NetworkPolicy, ResourceQuota), and unregisters its card from the registry.

**Example Request:**
```bash
curl -s -X DELETE http://localhost:9000/agents/log-analyzer-01
```

**Response `204 No Content`**

---

## A2A Card Registry & Handshake Endpoints

### `GET /agents/{agent_id}/card`
A2A peer-discovery endpoint. Returns the registered A2A Agent Card for the given agent.

**Response `200 OK`**
```json
{
  "id": "log-analyzer-01",
  "name": "log-analyzer",
  "description": "Analyzes system logs for errors and anomalies.",
  "version": "0.1.0",
  "endpoint": "http://log-analyzer-01-runner.log-analyzer-01.svc.cluster.local:8000",
  "capabilities": { "streaming": true, "pushNotifications": false },
  "skills": [{ "id": "analyze-logs", "name": "analyze-logs" }]
}
```

---

### `POST /agents/{agent_id}/handshake`
Called by the runner pod at startup to push its A2A Agent Card directly to the Control Plane broker.

**Request Body:**
```json
{
  "card": {
    "id": "log-analyzer-01",
    "name": "log-analyzer",
    "description": "Analyzes system logs.",
    "version": "0.1.0",
    "endpoint": "http://log-analyzer-01-runner.log-analyzer-01.svc.cluster.local:8000",
    "capabilities": { "streaming": true },
    "skills": [{ "id": "analyze-logs" }]
  }
}
```

**Response `200 OK`**
```json
{
  "registered": true,
  "agent_id": "log-analyzer-01"
}
```

---

## WebSocket Chat Proxy Endpoint

### `WS /chat/{agent_id}`
Proxies bidirectional streaming chat messages between an external client and the runner pod inside Kubernetes.

- **Query Parameters:**
  - `conversation_id` *(optional)*: Identifier of an existing conversation. Enables multi-session history isolation and automatic naming.

- **Close codes:**
  - `4404`: Agent or conversation not found.
  - `4503`: Agent is not in `RUNNING` status.
  - `1011`: Communication proxy error.

---

## Conversation Management Endpoints

### `POST /agents/{agent_id}/conversations`
Creates a new named conversation session for an agent.

**Request Body:**
```json
{
  "conversation_id": "conv-101",
  "name": "Incident Investigation"
}
```

**Response `201 Created`**
```json
{
  "conversation_id": "conv-101",
  "agent_id": "log-analyzer-01",
  "name": "Incident Investigation",
  "created_at": "2026-09-01T10:00:00.000000Z",
  "updated_at": "2026-09-01T10:00:00.000000Z"
}
```

---

### `GET /agents/{agent_id}/conversations`
Lists all conversations associated with an agent, sorted by creation timestamp.

**Response `200 OK`**
```json
[
  {
    "conversation_id": "conv-101",
    "agent_id": "log-analyzer-01",
    "name": "Incident Investigation",
    "created_at": "2026-09-01T10:00:00.000000Z",
    "updated_at": "2026-09-01T10:00:00.000000Z"
  }
]
```

---

### `DELETE /agents/{agent_id}/conversations/{conversation_id}`
Deletes a conversation session and immediately closes any active WebSocket connections attached to it.

**Response `204 No Content`**

---

## A2A Task Management & Delegation Endpoints

### `POST /agents/{agent_id}/tasks`
Submits an asynchronous A2A task to an agent (fire-and-forget).

**Request Body:**
```json
{
  "message": "Analyze error spike between 09:00 and 10:00 UTC",
  "source": "cli"
}
```

**Response `202 Accepted`**
```json
{
  "task_id": "task-8f92a1",
  "agent_id": "log-analyzer-01",
  "status": "submitted",
  "source": "cli",
  "message": "Analyze error spike between 09:00 and 10:00 UTC",
  "result": null,
  "created_at": "2026-09-01T10:05:00.000000",
  "updated_at": "2026-09-01T10:05:00.000000"
}
```

---

### `GET /agents/{agent_id}/tasks`
Lists all tasks (submitted via API or triggered by background schedules) for an agent.

**Response `200 OK`**
```json
[
  {
    "task_id": "task-8f92a1",
    "agent_id": "log-analyzer-01",
    "status": "completed",
    "source": "cli",
    "message": "Analyze error spike between 09:00 and 10:00 UTC",
    "result": "Found 42 HTTP 500 errors caused by database connection timeout.",
    "created_at": "2026-09-01T10:05:00.000000",
    "updated_at": "2026-09-01T10:06:12.000000"
  }
]
```

---

### `GET /agents/{agent_id}/tasks/{task_id}`
Retrieves the status and result of a specific task.

**Response `200 OK`**
```json
{
  "task_id": "task-8f92a1",
  "agent_id": "log-analyzer-01",
  "status": "completed",
  "source": "cli",
  "message": "Analyze error spike between 09:00 and 10:00 UTC",
  "result": "Found 42 HTTP 500 errors caused by database connection timeout.",
  "created_at": "2026-09-01T10:05:00.000000",
  "updated_at": "2026-09-01T10:06:12.000000"
}
```

---

### `PATCH /agents/{agent_id}/tasks/{task_id}`
Updates the status and optional result of a task during its execution lifecycle (`submitted → working → completed / failed`).

**Request Body:**
```json
{
  "status": "completed",
  "result": "Task finished successfully"
}
```

**Response `200 OK`**
```json
{
  "task_id": "task-8f92a1",
  "agent_id": "log-analyzer-01",
  "status": "completed",
  "source": "cli",
  "message": "Analyze error spike between 09:00 and 10:00 UTC",
  "result": "Task finished successfully",
  "created_at": "2026-09-01T10:05:00.000000",
  "updated_at": "2026-09-01T10:06:12.000000"
}
```

---

### `POST /agents/{source_agent_id}/delegate`
Brokers an A2A task delegation from a source agent to a target agent.

**Request Body:**
```json
{
  "target_agent_id": "report-writer-01",
  "message": "Generate incident summary report from log analysis"
}
```

**Response `201 Created`**
```json
{
  "task_id": "task-99b1c2",
  "source_agent_id": "log-analyzer-01",
  "target_agent_id": "report-writer-01",
  "status": "submitted"
}
```
