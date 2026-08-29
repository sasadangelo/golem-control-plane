# Golem vs OpenClaw — Feature Comparison

> **Disclaimer:** OpenClaw is an open-source project developed by the OpenClaw Foundation. This comparison is based on its public repository and documentation. Golem's side reflects the current state of MVP 1 plus the planned roadmap.
>
> OpenClaw homepage: [openclaw.ai](https://openclaw.ai) · Repository: [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)

---

## At a glance

| | Golem | OpenClaw |
|---|---|---|
| **Primary purpose** | Kubernetes-native platform to deploy, isolate, and orchestrate autonomous AI agents | Personal / team AI assistant that runs on your devices and connects to messaging channels |
| **Target user** | Engineering teams, platform operators | Individual users, small teams |
| **Written in** | Python | TypeScript |
| **Open source** | ✅ MIT | ✅ MIT |
| **Deployment** | Kubernetes (Docker / process on roadmap) | macOS, Linux, Windows, Docker, VPS |

---

## Legend

| Symbol | Meaning |
|:---:|---|
| ✅ | Feature present / available |
| ❌ | Feature absent |
| 🔜 | Planned on Golem roadmap |
| ⚠️ | Partial / limited support |
| ❓ | Unknown / not publicly documented |

---

## 1. Deployment & Hosting Model

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Self-hosted | ✅ | ✅ |
| Kubernetes-native | ✅ | ❌ |
| Docker / local (no K8s) | 🔜 MVP 4 | ✅ |
| Runs as a background daemon on laptop / desktop | ❌ | ✅ |
| VPS / server deployment | ✅ (K8s) | ✅ |
| Offline / air-gapped (local models) | 🔜 MVP 2 (Ollama) | ✅ (Ollama + local models) |
| Per-agent isolated namespace (K8s) | ✅ | ❌ |
| Resource quotas per agent (CPU / memory) | ✅ | ❌ |
| TTL-based garbage collection | ✅ | ❌ |
| Network policy per agent (egress control) | ✅ | ❌ |
| Multi-user (team) deployment | 🔜 MVP 6 | ✅ (shared Gateway) |
| Personal single-user mode | ✅ (MockProvisioner) | ✅ (primary mode) |

---

## 2. Model & Provider Support

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| IBM WatsonX / Granite | ✅ | ❓ |
| OpenAI | 🔜 MVP 2 | ✅ |
| Anthropic Claude | 🔜 Phase 3 | ✅ |
| Google Gemini | ❌ | ✅ |
| Ollama (local models) | 🔜 MVP 2 | ✅ |
| Groq | ❌ | ✅ |
| Mistral | ❌ | ✅ |
| Model failover / fallback | ❌ | ✅ |
| Switch model per-agent (no rebuild) | 🔜 MVP 2 | ✅ |
| Multi-provider in same platform | 🔜 MVP 2 | ✅ |
| Usage tracking / token accounting | 🔜 MVP 4 | ✅ |

---

## 3. Agent Architecture & Capabilities

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| ReAct loop (reason + act) | ✅ | ✅ |
| Multi-step planning / deep agent | 🔜 MVP 5 | ✅ |
| Subagents / parallel specialist lanes | ❌ | ✅ |
| Agent swarm | ❌ | ✅ (`swarm`) |
| Persistent agent identity (`AGENTS.md`) | ✅ | ✅ (`soul.md` / system prompt) |
| Declarative skill injection (`SKILL.md`) | ✅ | ✅ (skills system) |
| Skill workshop (create/edit skills in-session) | ❌ | ✅ |
| Custom graph logic upload (no rebuild) | 🔜 MVP 5 | ❌ |
| LangGraph orchestration | ✅ | ❌ (TypeScript runtime) |
| Background Cron / Timer triggers | ✅ | ✅ (standing intents / automation) |
| Webhook trigger | ✅ | ✅ |
| A2A protocol (Agent-to-Agent) | ✅ | ✅ (A2A 1.0 JSON-RPC) |
| Agent Card (`/.well-known/agent.json`) | ✅ | ✅ (`/.well-known/agent-card.json`) |
| A2A outbound (send to peer agents) | ✅ | ✅ |
| A2A inbound (receive from peer agents) | ✅ | ✅ |
| A2A streaming / SSE | ❌ | ❌ (not yet supported) |
| Multi-agent cooperation | ✅ (A2A) | ✅ (A2A + subagents) |

---

## 4. MCP Support

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| MCP client (connect to external MCP servers) | ✅ | ✅ |
| MCP server (expose OpenClaw as MCP server) | ❌ | ✅ (`openclaw mcp serve`) |
| MCP transports: Stdio | ✅ | ✅ |
| MCP transports: SSE | ✅ | ✅ |
| MCP transports: Streamable HTTP | ❌ | ✅ |
| MCP OAuth authentication | ❌ | ✅ (`openclaw mcp login`) |
| MCP tool filter (include / exclude per server) | ❌ | ✅ |
| MCP Registry (reusable named servers platform-wide) | 🔜 MVP 3 | ❌ |
| MCP management UI (Settings → MCP) | ❌ | ✅ |
| MCP CLI management (`mcp add/status/doctor/probe`) | ❌ | ✅ |

---

## 5. Messaging Channels

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| WebSocket chat (CLI / API clients) | ✅ | ✅ |
| Web Control UI | 🔜 Phase 3 | ✅ |
| Telegram | ❌ | ✅ |
| WhatsApp | ❌ | ✅ |
| Slack | ❌ | ✅ |
| Discord | ❌ | ✅ |
| iMessage | ❌ | ✅ |
| Signal | ❌ | ✅ |
| Google Chat | ❌ | ✅ |
| Microsoft Teams | ❌ | ✅ |
| Matrix | ❌ | ✅ |
| IRC | ❌ | ✅ |
| SMS | ❌ | ✅ |
| Mattermost | ❌ | ✅ |
| WeChat / WeCom | ❌ | ✅ |
| Twitch | ❌ | ✅ |
| A2A channel (external agent interop) | ✅ | ✅ |

---

## 6. Tools & Integrations

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Shell / bash execution | ✅ | ✅ |
| Web search (Brave, Perplexity, DuckDuckGo, Exa, Tavily…) | ❌ | ✅ (multiple providers) |
| Browser control / computer use | ❌ | ✅ |
| Screen capture | ❌ | ✅ |
| PDF reading | ❌ | ✅ |
| Image generation | ❌ | ✅ |
| Video generation | ❌ | ✅ |
| Music generation | ❌ | ✅ |
| Text-to-speech (TTS) | ❌ | ✅ |
| Code execution sandbox | ❌ | ✅ |
| File read / write | ✅ | ✅ |
| HTTP / external API tool | ✅ | ✅ |
| Slash commands | ❌ | ✅ |

---

## 7. Memory & State

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Multi-turn conversation | ✅ | ✅ |
| Auto-titling of conversations | ✅ | ❓ |
| Persistent state (survives restart) | 🔜 MVP 4 (Redis) | ✅ (SQLite) |
| Long-term memory (automatic) | ❌ | ✅ (multiple memory backends) |
| Memory search | ❌ | ✅ |
| Context compaction / rolling summary | 🔜 MVP 4 | ✅ |
| Active memory (in-context working memory) | ❌ | ✅ |
| Project-scoped context workspaces | 🔜 MVP 6 | ✅ (agent workspaces) |
| Session search | ❌ | ✅ |
| Dreaming (offline background memory consolidation) | ❌ | ✅ |

---

## 8. CLI & Developer Experience

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Dedicated CLI tool | ✅ (`golem`) | ✅ (`openclaw`) |
| Interactive TUI chat | ✅ (`golem chat`) | ✅ |
| Multi-context CLI (manage multiple control planes) | ✅ | ❌ |
| Agent lifecycle management via CLI | ✅ (`golem agent *`) | ⚠️ (Gateway-managed) |
| Conversation management via CLI | ✅ (`golem conv *`) | ✅ |
| REST API for agent lifecycle | ✅ | ✅ (Gateway API) |
| WebSocket streaming | ✅ | ✅ |
| Plugin / extension SDK | ❌ | ✅ (TypeScript plugin SDK) |
| Plugin marketplace (ClawHub) | 🔜 Phase 3 (Skill Marketplace) | ✅ (clawhub.ai) |
| Onboarding wizard | ❌ | ✅ (`openclaw onboard`) |
| Doctor / self-repair CLI | ❌ | ✅ (`openclaw doctor --fix`) |
| Helm Chart for K8s deploy | 🔜 MVP 4 | ❌ |
| OpenAPI / Swagger spec | ✅ | ✅ |

---

## 9. Security & Isolation

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Per-agent K8s namespace isolation | ✅ | ❌ |
| Network policy per agent (egress control) | ✅ | ❌ |
| Secrets via K8s Secrets (never baked in image) | ✅ | N/A |
| Secrets management for tools / channels | ✅ (K8s Secrets) | ✅ (secrets store) |
| RBAC | ✅ (K8s) | ⚠️ (access groups) |
| Multi-tenancy | 🔜 MVP 6 | ✅ (trusted team Gateway) |
| Inbound message pairing / approval | ❌ | ✅ (`openclaw pairing approve`) |
| Tool call execution approval | ❌ | ✅ (exec approvals + permission modes) |
| Sandboxing for tool execution | ❌ | ✅ (configurable) |
| A2A bearer token per peer | ✅ | ✅ |
| No telemetry by default | ❌ | ✅ (opt-in only) |
| Data sovereignty (fully on-prem) | ✅ | ✅ |
| Signed Agent Cards (zero-trust A2A) | 🔜 Phase 3 | ❌ |

---

## 10. Observability

| Feature | Golem | OpenClaw |
|---|:---:|:---:|
| Structured logging | ✅ (Loguru) | ✅ |
| LLM tracing | 🔜 MVP 4 (Langfuse) | ⚠️ (usage tracking) |
| Token usage metrics | 🔜 MVP 4 | ✅ |
| Health probes (`/health`) | ✅ | ✅ |
| Session recording | ❌ | ✅ |
| Diagnostics CLI | ❌ | ✅ (`openclaw doctor`) |

---

## Summary

### Where Golem wins

- **Hard per-agent isolation** — dedicated K8s namespace, NetworkPolicy, ResourceQuota. Golem's isolation model has no equivalent in OpenClaw; each agent is truly sandboxed at the infrastructure level.
- **Platform-grade lifecycle management** — programmatic `create / list / delete / status` for agent sandboxes via REST API and CLI; OpenClaw is a single Gateway, not a multi-agent provisioner.
- **TTL Garbage Collection** — automatic sandbox cleanup without operator action.
- **Multi-context CLI** — manage multiple Golem control planes from one tool, scriptable end-to-end.
- **Declarative skills via files** (`SKILL.md`) — skills are version-controlled plain text, mounted at runtime, no GUI required.
- **Background automations** (Cron, Timer, Webhook) as first-class runner primitives.
- **IBM WatsonX / Granite** support out of the box.

### Where OpenClaw wins

- **Messaging channels** — WhatsApp, Telegram, Slack, Discord, iMessage, Signal, Teams, Matrix and 20+ more. Golem has no channel integrations today.
- **Rich tool ecosystem** — browser control, web search (multiple providers), image/video/music generation, TTS, PDF, screen capture, code execution. All absent in Golem today.
- **MCP server mode** — OpenClaw can expose itself as an MCP server to other clients; Golem is MCP-client only.
- **Advanced memory** — multiple backends, memory search, context compaction, dreaming (background consolidation), active memory.
- **Plugin SDK + ClawHub marketplace** — extend with TypeScript plugins, discover community skills/MCP bundles.
- **Subagents and swarms** — parallel specialist lanes and agent swarms built-in.
- **Onboarding and self-repair** (`openclaw onboard`, `openclaw doctor --fix`).
- **Web Control UI** — fully featured today; Golem's Web UI is Phase 3.
- **No telemetry by default** — OpenClaw sends no analytics unless the operator opts in.
- **Broader model support** — OpenAI, Claude, Gemini, Groq, Mistral, Ollama all supported today.

### Both support

- A2A 1.0 protocol (Agent Card + bidirectional task delegation)
- MCP client (connect to external MCP servers)
- Open source (MIT)
- Self-hosted, data-sovereign deployment
- Background automation triggers
- Skills / declarative agent identity

### The key distinction

Golem is a **Kubernetes-native agent platform** — its strength is running many isolated agents securely on infrastructure, with hard boundaries, lifecycle management, and A2A interoperability between services. OpenClaw is a **personal / team AI assistant** — its strength is meeting you where you already communicate (WhatsApp, Telegram, Slack…) with a rich tool ecosystem and multi-provider model support. They are complementary: an OpenClaw Gateway could delegate tasks to Golem-hosted specialist agents via A2A, and Golem agents could in principle use OpenClaw's MCP server to access its tool ecosystem.
