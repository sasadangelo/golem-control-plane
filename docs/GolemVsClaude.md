# Golem vs Claude — Feature Comparison

> **Disclaimer:** Claude's internal architecture is not publicly documented. This comparison is based on observable behaviour, known product features, and publicly available information. It is necessarily incomplete on Claude's side. Golem's side reflects the current state of MVP 1 plus the planned roadmap.

---

## Legend

| Symbol | Meaning |
|:---:|---|
| ✅ | Feature present / available |
| ❌ | Feature absent |
| 🔜 | Planned on roadmap |
| ❓ | Unknown / not publicly documented |

---

## 1. Deployment & Infrastructure

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Self-hosted, runs on your own infrastructure | ✅ | ❌ |
| Cloud-only offering | ❌ | ✅ |
| Kubernetes-native deployment | ✅ | ❓ |
| Docker / local deployment (no K8s) | 🔜 MVP 4 | ❌ |
| Offline / air-gapped operation | 🔜 MVP 2 (Ollama) | ❌ |
| Per-agent isolated namespace | ✅ | ❓ |
| Resource quotas per agent (CPU / memory) | ✅ | ❌ |
| TTL-based automatic garbage collection | ✅ | ❌ |
| Network policy (default-deny egress) | ✅ | ❓ |
| Serverless / scale-to-zero | 🔜 Phase 3 | ❓ |

---

## 2. Model & Provider Support

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| IBM WatsonX / Granite models | ✅ | ❌ |
| Anthropic Claude models | 🔜 Phase 3 | ✅ |
| OpenAI-compatible endpoint | 🔜 MVP 2 | ❌ |
| Ollama (local open-source models) | 🔜 MVP 2 | ❌ |
| vLLM | 🔜 MVP 2 | ❌ |
| Hugging Face TGI | 🔜 Phase 3 | ❌ |
| Switch model at runtime (no rebuild) | 🔜 MVP 2 | ❌ |
| Multi-provider in the same platform | 🔜 MVP 2 | ❌ |

---

## 3. Agent Capabilities

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| ReAct agentic loop (reason + act) | ✅ | ✅ |
| Tool / function calling | ✅ (MCP) | ✅ |
| Multi-step task planning (`loop: deep`) | 🔜 MVP 5 | ✅ (extended thinking) |
| Persistent agent identity (`AGENTS.md`) | ✅ | ❌ (per-session system prompt only) |
| Declarative skill injection (`SKILL.md`) | ✅ | ❌ |
| Custom graph logic upload (`pipeline.py`) | 🔜 MVP 5 | ❌ |
| LangGraph-based orchestration | ✅ | ❓ |
| CrewAI backend | 🔜 Phase 3 | ❌ |
| AutoGen backend | 🔜 Phase 3 | ❌ |
| Background automation triggers (Cron, Timer, Webhook) | ✅ | ❌ |
| Agent-to-Agent (A2A) delegation | ✅ | ❌ |
| Agent Card (`/.well-known/agent.json`) | ✅ | ❌ |

---

## 4. Context & Memory

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Multi-turn conversation support | ✅ | ✅ |
| Named conversation management | ✅ | ✅ (projects) |
| Auto-titling of conversations | ✅ | ✅ |
| Persistent conversation history (across restarts) | 🔜 MVP 4 (Redis) | ✅ |
| Conversation rolling summary (token-limit guard) | 🔜 MVP 4 | ❓ |
| Long context window (200K tokens) | ❌ (model-dependent) | ✅ (Claude 3.x) |
| Project-scoped context workspaces | 🔜 MVP 6 | ✅ (Claude Projects) |
| File / document upload to context | ❌ | ✅ |
| Vision / image input | ❌ | ✅ |

---

## 5. Tool Use & Integrations

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| MCP (Model Context Protocol) client | ✅ | ✅ (Claude Desktop / API) |
| MCP Registry (reusable named servers) | 🔜 MVP 3 | ❌ |
| Shared vs dedicated MCP server modes | 🔜 MVP 3 | ❌ |
| Built-in bash tool | ✅ | ✅ (Claude Code) |
| Web search | ❌ | ✅ (claude.ai) |
| Code execution sandbox | ❌ | ✅ (claude.ai) |
| Computer use / browser control | ❌ | ✅ (Claude API beta) |
| External API HTTP tool | ✅ (`http_check`) | ✅ |
| Skill Marketplace | 🔜 Phase 3 | ❌ |

---

## 6. Developer & API Surface

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| REST API for agent lifecycle | ✅ | ✅ |
| WebSocket streaming chat | ✅ | ✅ (SSE) |
| CLI tool (`golem` / `claude`) | ✅ | ✅ (Claude Code) |
| Multi-context CLI (kubectl-style) | ✅ | ❌ |
| Programmatic agent creation via API | ✅ | ❌ (model only, no agent lifecycle) |
| Batch / async API | ❌ | ✅ |
| SDK (Python / JS) | ❌ | ✅ |
| OpenAPI spec | ✅ | ✅ |
| Webhook trigger for agents | ✅ | ❌ |

---

## 7. Security

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Kubernetes RBAC (least-privilege) | ✅ | ❓ |
| Secrets injected via K8s Secrets (never in image) | ✅ | N/A |
| Network policy per agent (egress control) | ✅ | ❓ |
| Multi-tenancy (per-account isolation) | 🔜 MVP 6 | ✅ |
| API key authentication | ✅ (runner-side) | ✅ |
| JWT / OAuth for the control plane | 🔜 MVP 6 | ✅ |
| Signed Agent Cards (zero-trust A2A) | 🔜 Phase 3 | N/A |
| gVisor / Kata Containers runtime isolation | 🔜 Phase 3 | ❓ |
| Graph plugin code signing | 🔜 Phase 3 | N/A |

---

## 8. Observability & Resilience

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Structured logging (Loguru) | ✅ | ❓ |
| LLM tracing with Langfuse | 🔜 MVP 4 | ❌ |
| Token usage and latency metrics | 🔜 MVP 4 | ✅ (API response headers) |
| Conversation state survives restart (Redis) | 🔜 MVP 4 | ✅ |
| Control plane state survives restart (PostgreSQL) | 🔜 MVP 4 | N/A |
| Health probes (`/health`) | ✅ | ❓ |
| Helm Chart for reproducible deploys | 🔜 MVP 4 | N/A |

---

## 9. UI & User Experience

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Web UI (chat + orchestration dashboard) | 🔜 Phase 3 | ✅ |
| CLI-first interface | ✅ | ✅ (Claude Code) |
| A2A task monitoring dashboard | 🔜 Phase 3 | N/A |
| Inline document editing | ❌ | ✅ (Artifacts) |
| Image / diagram generation | ❌ | ✅ |
| Voice input / output | ❌ | ❌ |
| Mobile app | ❌ | ✅ (claude.ai) |
| IDE integration (VS Code, JetBrains) | ❌ | ✅ (Claude Code) |

---

## 10. Platform & Ecosystem

| Feature | Golem | Claude (claude.ai / API) |
|---|:---:|:---:|
| Open source | ✅ | ❌ |
| Self-sovereign — you own the data | ✅ | ❌ |
| Multi-cloud portability | ✅ (K8s anywhere) | ❌ (Anthropic-hosted only) |
| OpenShift support | 🔜 Phase 3 | ❌ |
| Kubernetes Operator / CRD | 🔜 Phase 3 | ❌ |
| A2A standard (agent interoperability) | ✅ | ❌ |
| Skill Registry (versioned Git-backed) | 🔜 MVP 3 | ❌ |
| Model quality / reasoning capability | ⬇️ model-dependent | ⬆️ state-of-the-art |
| Commercially supported SLA | ❌ | ✅ |
| Usage-based pricing (pay per token) | depends on model | ✅ |
| Free to run (with your own hardware) | ✅ | ❌ |

---

## Summary

**Where Golem wins (or has a clear advantage):**
- Full infrastructure control — self-hosted, open source, runs anywhere Kubernetes runs.
- Per-agent isolation with hard security boundaries (RBAC, NetworkPolicy, ResourceQuota).
- Native multi-provider / multi-model flexibility (no lock-in).
- Agent-to-Agent (A2A) protocol for autonomous multi-agent cooperation.
- Declarative agent identity and skills (`AGENTS.md` / `SKILL.md`).
- Background automations (Cron, Timer, Webhook) running without user interaction.
- CLI-first platform management (create, inspect, delete, chat — all scriptable).
- Data sovereignty — all conversation data stays on your infrastructure.

**Where Claude wins (or has a clear advantage):**
- Raw reasoning and language quality — state-of-the-art LLM performance.
- Long context window (up to 200K tokens).
- Native vision, file upload, and computer use.
- Rich web UI with Artifacts, inline editing, Projects.
- Mature ecosystem: mobile app, IDE integrations, SDK, batch API.
- Persistent memory and state out of the box (no Redis setup needed).
- Production SLA and enterprise support.

**The key distinction:**  
Golem is an **open, programmable agent platform** — it manages *how* and *where* agents run, which model they use, and how they cooperate. Claude is a **highly capable closed AI service** optimised for direct human interaction. They solve different problems and can be complementary: Golem could in principle route to a Claude-compatible endpoint once the Anthropic backend lands in Phase 3.
