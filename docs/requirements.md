# Requirements — Golem
_Last updated: 2025-07-14_

## Overview

Golem is a Kubernetes-native **Agent-as-a-Service platform** that provisions isolated AI agent sandboxes on demand. Developers and operators create, configure, and interact with LLM-powered agents through a REST/WebSocket control plane and a CLI. Agents can communicate with each other via the Agent-to-Agent (A2A) protocol, be triggered by background automations, and be extended with skills and MCP tool servers.

---

## Actors

| Actor                 | Description                                                                                          | Type   |
| :-------------------- | :--------------------------------------------------------------------------------------------------- | :----- |
| `Developer`           | Creates and manages agents via the CLI or API; configures personas, skills, and tools                | Human  |
| `Operator`            | Deploys and administers the control plane on Kubernetes; manages contexts and cluster resources      | Human  |
| `End User`            | Interacts with an agent in real time via `golem chat` or a WebSocket client                          | Human  |
| `Agent`               | An autonomous LLM-powered runner that executes tasks, uses tools, and delegates to other agents      | System |
| `Golem CLI`           | Command-line client that proxies operator and developer intent to the control plane                  | System |
| `Control Plane`       | FastAPI service that provisions sandboxes, manages conversation state, and proxies WebSocket traffic | System |
| `External MCP Server` | A third-party tool server connected to an agent at runtime                                           | System |

---

## Job Stories

### Actor: Developer

#### JS-001 — Create an agent on Kubernetes
**When** I want to run an AI agent for a specific task,
**I want to** issue a single CLI command that provisions an isolated sandbox (namespace, pod, config) on Kubernetes,
**so that** the agent is available without manual cluster configuration.

**Acceptance criteria:**
- **Given** a running control plane and a valid `config.yaml`, **When** I run `golem agent create`, **Then** a Kubernetes namespace, pod, ConfigMap, ResourceQuota, and NetworkPolicy are created and the agent reaches `RUNNING` status.
- **Given** an agent that has been running past its TTL, **When** the garbage collector fires, **Then** the sandbox is automatically deleted.
- **Given** an invalid `config.yaml`, **When** I run `golem agent create`, **Then** the CLI returns a clear validation error and no Kubernetes resources are created.

**Edge cases / notes:**
- The provisioner must apply least-privilege RBAC (ClusterRole) and default-deny egress NetworkPolicy for every sandbox.

---

#### JS-002 — Inject a persona and skills into an agent
**When** I want an agent to behave according to a specific role or have access to declarative skills,
**I want to** supply an `AGENTS.md` persona file and one or more `SKILL.md` files at creation time,
**so that** the agent's system prompt and tool set are automatically configured without code changes.

**Acceptance criteria:**
- **Given** an `AGENTS.md` file, **When** the agent runner starts, **Then** the persona content is injected into the system prompt.
- **Given** a `SKILL.md` file, **When** the agent runner starts, **Then** the skill is available for the agent to invoke.

---

#### JS-003 — Connect MCP tool servers to an agent
**When** I want an agent to use external tools (e.g. file system, databases, APIs),
**I want to** configure one or more MCP servers in the agent's `config.yaml`,
**so that** the agent can discover and call their tools without writing custom integration code.

**Acceptance criteria:**
- **Given** one or more MCP server entries in `config.yaml`, **When** the agent runner starts, **Then** it connects to each configured server and makes their tools available to the agent.
- **Given** an MCP server that is unreachable at startup, **When** the runner initialises, **Then** the error is logged and the runner continues with the remaining servers.

---

#### JS-004 — List, inspect, and delete agents
**When** I need to manage the lifecycle of running agents,
**I want to** list all agents, view their status, and delete them by name from the CLI,
**so that** I can audit and clean up sandboxes without touching the cluster directly.

**Acceptance criteria:**
- **Given** one or more running agents, **When** I run `golem agent list`, **Then** a table of agents with name, status, and creation time is printed.
- **Given** a running agent, **When** I run `golem agent status <name>`, **Then** the current pod phase and health are shown.
- **Given** a running agent, **When** I run `golem agent delete <name>`, **Then** all associated Kubernetes resources are removed.

---

#### JS-013 — Update an agent's configuration
**When** I want to change the behaviour of a running agent (persona, skills, or config),
**I want to** supply updated `AGENTS.md`, `SKILL.md`, and/or `config.yaml` files via `golem agent update`,
**so that** the agent restarts with the new configuration without losing its identity, conversations, or having to recreate the sandbox from scratch.

**Acceptance criteria:**
- **Given** a running agent, **When** I run `golem agent update <name>` with one or more updated files, **Then** the control plane updates the ConfigMap, restarts the pod, and the agent reaches `RUNNING` status with the new configuration.
- **Given** an agent being updated, **When** the pod is restarting, **Then** the agent status is `UPDATING` and no new conversations or tasks are accepted.
- **Given** an agent update, **When** it completes successfully, **Then** `agent_id`, `name`, and `namespace` are unchanged, and existing conversations are preserved.
- **Given** tasks in `submitted` or `running` status at update time, **When** the pod restarts, **Then** those tasks transition to `failed` with reason `agent_updated`.
- **Given** an invalid updated `config.yaml`, **When** I run `golem agent update`, **Then** the CLI returns a validation error and the agent remains in its current state.

**Edge cases / notes:**
- `agent_id`, `name`, and `namespace` are immutable and cannot be changed via update.
- Only `AGENTS.md` (Persona), `SKILL.md` files (Skills), and `config.yaml` (automations, LLM config, MCP servers, TTL) are updatable.

---

#### JS-005 — Manage automations (cron, timer, webhook)
**When** I want an agent to act on a schedule or in response to an external event,
**I want to** configure background triggers (Cron, Timer, Webhook) in the agent's config,
**so that** the agent runs tasks automatically without a human initiating each one.

**Acceptance criteria:**
- **Given** a Cron trigger in `config.yaml`, **When** the schedule fires, **Then** the agent executes the configured task.
- **Given** a Timer trigger, **When** the interval elapses, **Then** the agent executes the configured task.
- **Given** a Webhook trigger and an inbound HTTP POST to its endpoint, **When** the request arrives, **Then** the agent executes the configured task with the payload as input.

---

### Actor: End User

#### JS-006 — Chat with an agent in real time
**When** I want to interact conversationally with an agent,
**I want to** open a chat session via `golem chat` that streams the agent's replies,
**so that** I can have a back-and-forth dialogue with full response streaming.

**Acceptance criteria:**
- **Given** a running agent, **When** I run `golem chat <agent-name>`, **Then** a WebSocket connection is established and the agent's streaming responses are printed as they arrive.
- **Given** an active chat session, **When** I send a message, **Then** the agent's reply is streamed back within a reasonable time.
- **Given** a conversation that has been closed, **When** I reconnect, **Then** a new `conversation_id` is assigned.

---

#### JS-007 — Manage conversations
**When** I want to review or organise my past interactions,
**I want to** list conversations, view their titles, and delete ones I no longer need,
**so that** I can navigate my history without scrolling through a single unbounded log.

**Acceptance criteria:**
- **Given** one or more past conversations, **When** I run `golem conv list`, **Then** a table with conversation IDs, auto-generated titles, and dates is shown.
- **Given** a conversation, **When** it ends, **Then** the control plane auto-generates a short title from the exchange content.
- **Given** a conversation ID, **When** I run `golem conv delete <id>`, **Then** the conversation and its messages are removed.

---

### Actor: Agent

#### JS-008 — Use built-in tools for shell commands and HTTP health checks
**When** the agent needs to interact with the operating system or verify a remote endpoint,
**I want to** call the built-in `execute_command` and `http_check` tools,
**so that** the agent can automate system tasks and probe external services without extra configuration.

**Acceptance criteria:**
- **Given** a request to run a shell command, **When** `execute_command` is called, **Then** the command runs in the sandbox and its stdout/stderr is returned to the agent.
- **Given** a request to check a URL, **When** `http_check` is called, **Then** the HTTP status code and latency are returned.

---

#### JS-009 — Delegate a task to another agent (A2A)
**When** an agent cannot or should not handle a task itself,
**I want to** delegate that task to another agent using the A2A protocol,
**so that** agents can collaborate without human coordination.

**Acceptance criteria:**
- **Given** a running target agent, **When** the delegating agent calls `POST /agents/{id}/delegate`, **Then** the task is created on the target with status `submitted`.
- **Given** a submitted task, **When** the target agent completes it, **Then** the task status transitions to `completed` and the result is returned to the delegating agent.
- **Given** a submitted task that cannot be completed, **When** the target agent encounters an error, **Then** the task status transitions to `failed` with an error message.

---

#### JS-010 — Publish an Agent Card for discovery
**When** an agent runner starts,
**I want to** automatically publish an Agent Card at `/.well-known/agent.json`,
**so that** other agents and orchestrators can discover my capabilities via a standard endpoint.

**Acceptance criteria:**
- **Given** a running agent, **When** a GET request is made to `/.well-known/agent.json`, **Then** a valid Agent Card JSON is returned with the agent's name, capabilities, and endpoint.
- **Given** a push handshake from another agent (`POST /agents/{id}/handshake`), **When** the runner receives it, **Then** the remote agent is registered and its card is stored for future delegation.
- **Given** a failed push handshake, **When** the runner retries, **Then** it falls back to pulling the card directly from the remote endpoint.

---

### Actor: Operator

#### JS-011 — Manage multiple control plane contexts
**When** I operate Golem across multiple clusters or environments (dev / staging / prod),
**I want to** register named control plane endpoints and switch between them with a single command,
**so that** I can target the right environment without editing config files by hand.

**Acceptance criteria:**
- **Given** a control plane URL and a name, **When** I run `golem cp add <name> <url>`, **Then** the context is saved.
- **Given** multiple contexts, **When** I run `golem cp use <name>`, **Then** subsequent commands target that control plane.
- **Given** multiple contexts, **When** I run `golem cp list`, **Then** all registered contexts are shown with the active one marked.

---

#### JS-012 — Enforce resource isolation per agent
**When** multiple agents run in the same cluster,
**I want to** ensure each agent is confined to its own namespace with CPU/memory quotas and network isolation,
**so that** a misbehaving agent cannot starve or reach other agents or cluster services.

**Acceptance criteria:**
- **Given** a provisioned agent sandbox, **When** I inspect the cluster, **Then** it has its own namespace, ResourceQuota, and a default-deny egress NetworkPolicy.
- **Given** an agent's pod, **When** it tries to contact another agent's pod directly, **Then** the connection is blocked by the NetworkPolicy.
- **Given** secrets needed by the agent, **When** the pod starts, **Then** secrets are injected via `envFrom` (not hardcoded in ConfigMap or environment variables).

---

## Business Constraints

1. Each agent sandbox must be isolated at the Kubernetes namespace level — no shared namespaces between agents.
2. Integer PKs / internal IDs must never be exposed in public API responses.
3. The control plane must not store LLM conversation content in a durable database in MVP 1 (in-memory or ephemeral).
4. The TTL garbage collector must be always-on — orphaned sandboxes must not accumulate.
5. Agent secrets must be injected via Kubernetes secrets / `envFrom`, never hardcoded in `config.yaml`.

---

## Non-Functional Requirements

| Category      | Requirement                                                                                     |
| :------------ | :---------------------------------------------------------------------------------------------- |
| Performance   | WebSocket chat must stream the first token within 3 seconds under normal load                   |
| Availability  | Control plane pod must restart automatically on crash (Kubernetes restart policy)               |
| Security      | Least-privilege RBAC ClusterRole; default-deny egress NetworkPolicy per sandbox; no PII in logs |
| Portability   | Control plane and runner must run on any Kubernetes 1.27+ cluster                               |
| Observability | All provisioning and GC actions must be logged at INFO level with agent ID and timestamp        |

---

## Out of Scope (MVP 1)

- Multi-provider LLM support (only WatsonX / `langchain-ibm` in MVP 1)
- Docker or process-based provisioners (Kubernetes only)
- Persistent conversation history in a database
- Multi-tenancy or user authentication on the control plane
- Interactive chat REPL (`golem shell`)
- Messaging channel adapters (Telegram, Slack, WhatsApp)

---

## Open Questions

- Should `conversation_id` be a UUID or an opaque token? (impacts CLI display)
- What is the maximum number of concurrent agents per cluster in a supported configuration?
- Should the Agent Card include the list of available skills, or only tools?

---

## Change Log

| Version | Date       | Change                                                                                      |
| :------ | :--------- | :------------------------------------------------------------------------------------------ |
| 0.1     | 2025-07-14 | Initial requirements — MVP 1 delivered features, seeded from `docs/roadmap.md`              |
| 0.2     | 2025-07-14 | Added JS-013 — agent update job story with acceptance criteria and invariants               |
