# Golem — Security Model

This document describes the security model of the Golem platform end-to-end — from Kubernetes RBAC to sandbox isolation, secrets management, and the roadmap toward hardened production deployments.

---

## Threat Model Summary

| Actor | Trust level | Attack surface |
|---|---|---|
| **Control Plane pod** | Trusted system component | K8s API Server — can create/delete Namespaces and Pods |
| **Agent Runner pod** | Untrusted workload | Restricted egress only; no access to K8s API |
| **Agent-to-Agent traffic** | Partially trusted | Validated via signed A2A Agent Cards (not iiplemented in Phase 1) |
| **External user** | Untrusted | REST/WebSocket API on Control Plane only |
| **CI/CD pipeline** | Trusted operator | Image build and push; no runtime access |

---

## 1. Kubernetes RBAC — Control Plane Identity

The Control Plane pod runs as a dedicated **ServiceAccount** (`golem-control-plane` in the `golem-system` namespace). It never uses the `default` ServiceAccount and never inherits cluster-admin privileges.

### Identity chain

```
ServiceAccount (golem-control-plane)
    └── ClusterRoleBinding
            └── ClusterRole (golem-control-plane)
                    ├── Namespaces      → get, list, create, delete
                    ├── Pods            → get, list, create, delete
                    ├── Pods/log        → get
                    ├── ResourceQuotas  → get, list, create, delete
                    └── NetworkPolicies → get, list, create, delete
```

### Why ClusterRole and not a namespaced Role?

The Control Plane must create **new Namespaces** at runtime (one per agent sandbox). Namespace creation is a cluster-scoped operation — it cannot be granted by a namespaced Role. Every other permission is restricted to the narrowest verb set required.

### What the Control Plane cannot do

- Cannot read or modify `Secrets` in any namespace (credentials are injected via env vars at pod creation time)
- Cannot modify `ClusterRole` or `ClusterRoleBinding` objects (no RBAC self-escalation)
- Cannot access `kube-system` or any other system namespace
- Cannot schedule `DaemonSets`, `Deployments`, or `StatefulSets` — only bare `Pods`

---

## 2. Agent Runner — No K8s Identity

Agent Runner pods run **without a ServiceAccount token** (`automountServiceAccountToken: false` — Phase 2 hardening). They have no ability to call the K8s API Server.

The runner's only communication channels are:

| Channel | Direction | Scope |
|---|---|---|
| HTTPS (port 443) | Egress | WatsonX API + declared MCP tool endpoints |
| DNS (port 53 UDP/TCP) | Egress | Name resolution only |
| HTTP (port 8000) | Ingress | A2A peer tasks + chat from Control Plane proxy |

All other egress is denied by the sandbox `NetworkPolicy`.

---

## 3. Sandbox Isolation

Each agent lives in its own **dedicated Kubernetes Namespace**. This provides three layers of isolation:

### 3.1 Network Isolation — NetworkPolicy

Every sandbox namespace gets a `NetworkPolicy` applied at creation time by the Provisioner:

```
Egress rules (allowlist):
  ✅  TCP port 443  — HTTPS to external APIs (WatsonX, MCP servers)
  ✅  UDP/TCP port 53 — DNS resolution
  ❌  All other egress — denied by default

Ingress rules:
  (not yet restricted at MVP — Phase 2 will add ingress allow-list)
```

> **Phase 2 hardening:** egress will be restricted to specific CIDRs per declared skill,
> rather than open HTTPS to the internet.

### 3.2 Resource Isolation — ResourceQuota

Each sandbox namespace has a `ResourceQuota` enforcing hard limits:

| Resource | Request limit | Hard limit |
|---|---|---|
| CPU | 500m | 1 core |
| Memory | 512 Mi | 1 Gi |

A misbehaving or compromised agent cannot starve other sandboxes of cluster resources.

### 3.3 Lifecycle Isolation — TTL Garbage Collection

The Control Plane runs a background GC coroutine that wakes up every `gc_interval` seconds and deletes any sandbox whose age has exceeded its `ttl_seconds`. Sandboxes without a TTL live until explicitly deleted.

**Defaults:**

| Parameter | Default | Meaning |
|---|---|---|
| `ttl_seconds` | `None` (no expiry) | Sandbox lives until `golem agent delete` is called |
| `gc_interval` | `60` s | How often the GC loop checks for expired sandboxes |

**How to create an ephemeral sandbox** (auto-deleted after N seconds):

```bash
# via the CLI — expires in 1 hour
golem agent create --config agent/config.yaml --ttl-seconds 3600

# via curl directly
curl -X POST http://localhost:9000/agents \
  -F "config=@agent/config.yaml" \
  -F "ttl_seconds=3600"
```

**How to change the GC polling interval** (`src/golem-control-plane/config.yaml`):

```yaml
control-plane:
  gc_interval: 30   # run GC every 30 seconds instead of 60
```

**Worst-case staleness:** a sandbox whose TTL expires at second 0 of a GC cycle will live at most one extra `gc_interval` before being collected.

---

## 4. Secrets Management

### MVP approach

WatsonX credentials (`WATSONX_API_KEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_MODEL_ID`) are stored as a **Kubernetes Secret** in `golem-system` and injected into agent pods as environment variables at provisioning time.

```
golem-system/Secret (golem-watsonx-credentials)
    └── injected as env vars → Agent Runner pod at creation
```

Credentials are **never embedded in image layers** — the `golem-runner` and `golem-control-plane` images contain no secrets. They are supplied at runtime exclusively via the Secret.

### Secret lifecycle rules

- `secret.yaml` is excluded from version control via `.gitignore`
- Only `secret.yaml.example` is committed (template with placeholder values)
- The `detect-secrets` pre-commit hook prevents accidental credential commits

### Phase 2 — External Secret Store

The K8s Secret approach will be replaced by an integration with **HashiCorp Vault** or an IBM Secrets Manager instance. The `ExternalSecret` CRD (via External Secrets Operator, already installed in the cluster) will pull credentials dynamically at pod startup, removing the need to store any secret material inside the cluster etcd.

---

## 5. Agent Card Trust — A2A Identity

Every Agent Runner pod publishes an **A2A Agent Card** at `/.well-known/agent.json`. The Control Plane Card Registry fetches and stores the card when the pod reaches `Running`.

### MVP

Cards are fetched over the cluster-internal network (ClusterIP). They are trusted implicitly because:
- Only the Control Plane can create pods in `golem-*` namespaces (RBAC)
- The card is fetched directly from the pod's ClusterIP — no external routing

### Phase 2 — Signed Cards

Agent Cards will be **cryptographically signed** (A2A v1.0 signing spec). The Card Registry will verify the signature before accepting registration, preventing a compromised sandbox from impersonating another agent.

---

## 6. Image Supply Chain

| Control | Detail |
|---|---|
| **No `latest` tag** | Images are pinned to explicit version tags (`v1`, `v2`, …) |
| **`IfNotPresent` pull policy** | Prevents unintended image replacement after initial load |
| **No secrets in layers** | Build-time secrets are never passed as `ENV` or `ARG` in Dockerfiles |
| **Minimal base image** | `python:3.12-slim` — no shell utilities beyond what the skill catalogue requires |

---

## 7. Security Roadmap

| Phase | Item |
|---|---|
| **Phase 2** | `automountServiceAccountToken: false` on all agent runner pods |
| **Phase 2** | NetworkPolicy ingress restrict: only allow traffic from `golem-system` namespace |
| **Phase 2** | NetworkPolicy egress restrict: per-skill CIDR allowlist instead of open HTTPS |
| **Phase 2** | Vault / External Secrets Operator integration — replace K8s Secrets |
| **Phase 2** | Signed A2A Agent Card validation in Card Registry |
| **Phase 3** | gVisor / Kata Containers runtime for dynamic code execution sandboxes |
| **Phase 3** | Multi-tenant RBAC — per-tenant ServiceAccount and Namespace isolation |
| **Phase 3** | Audit logging — all Control Plane API calls written to an immutable audit trail |
| **Phase 3** | Image signing (Sigstore / cosign) — verify image integrity before pod scheduling |
