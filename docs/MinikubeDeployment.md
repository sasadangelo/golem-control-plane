# Minikube Deployment Guide

This guide walks you through deploying the **Golem Control Plane** on a local **Minikube** Kubernetes cluster inside the dedicated `golem-system` namespace.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| [Minikube](https://minikube.sigs.k8s.io/) | latest | Local single-node Kubernetes cluster |
| [Podman](https://podman.io/) or [Docker](https://www.docker.com/) | 4+ | Container engine and image builder |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | 1.28+ | Kubernetes cluster management CLI |

---

## Step 1 — Start Minikube

Start Minikube configured with your preferred container runtime (e.g. `podman` or `docker`):

```bash
minikube start --driver=podman --container-runtime=containerd
```

Verify the cluster status:

```bash
kubectl cluster-info
```

---

## Step 2 — Build and Load Container Images

Build the Control Plane container image locally and load it into the Minikube environment:

```bash
# Build the localhost/golem-control-plane:v0.0.1 image
./build_images.sh

# Load the image into Minikube
./minikube/load_images.sh
```

*(Optional: If you are also testing agent provisioning, make sure to build and load the `localhost/golem-runner:v1` image into Minikube as well).*

---

## Step 3 — Configure WatsonX Secrets

Create the Kubernetes secret containing your WatsonX credentials:

```bash
cp deploy/golem-control-plane/secret.yaml.example deploy/golem-control-plane/secret.yaml
```

Edit `deploy/golem-control-plane/secret.yaml` with your real WatsonX credentials (base64 or stringData as specified in the template). **Never commit this file to git.**

---

## Step 4 — Deploy the Control Plane

Run the deployment script to apply the Kubernetes manifests in sequence:

```bash
./deploy.sh
```

This applies:
1. `deploy/golem-control-plane/namespace.yaml` (`golem-system`)
2. `deploy/golem-control-plane/serviceaccount.yaml`
3. `deploy/golem-control-plane/clusterrole.yaml`
4. `deploy/golem-control-plane/clusterrolebinding.yaml`
5. `deploy/golem-control-plane/secret.yaml`
6. `deploy/golem-control-plane/deployment.yaml`
7. `deploy/golem-control-plane/service.yaml`

and waits for the deployment rollout to complete.

---

## Step 5 — Verify and Access the Service

Port-forward the Control Plane service to your local machine:

```bash
# Keep this running in Terminal 1
kubectl -n golem-system port-forward svc/golem-control-plane 9000:9000
```

In a second terminal, verify the deployment:

```bash
# Liveness check
curl -s http://localhost:9000/health
# Output: {"status":"ok"}

# List agents
curl -s http://localhost:9000/agents
# Output: []
```

---

## Troubleshooting & Network Diagnostics

If runner pods or the control plane experience DNS or network routing issues inside Minikube, utility scripts are available in the `minikube/` folder:

```bash
# Check Minikube network connectivity
./minikube/check-minikube-network.sh

# Apply DNS and routing fixes if needed
./minikube/fix-minikube-network.sh
```
