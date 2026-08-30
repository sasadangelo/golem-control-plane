#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Deploy the Golem Control Plane to the current kubectl context.
#
# Usage:
#   ./deploy.sh
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../deploy/golem-control-plane"

echo "==> Deploying Golem Control Plane to context: $(kubectl config current-context)"

kubectl apply -f "${MANIFESTS_DIR}/namespace.yaml"
kubectl apply -f "${MANIFESTS_DIR}/serviceaccount.yaml"
kubectl apply -f "${MANIFESTS_DIR}/clusterrole.yaml"
kubectl apply -f "${MANIFESTS_DIR}/clusterrolebinding.yaml"
kubectl apply -f "${MANIFESTS_DIR}/secret.yaml" 2>/dev/null \
  || echo "WARN: secret.yaml not found — skipping (copy secret.yaml.example and fill in credentials)"
kubectl apply -f "${MANIFESTS_DIR}/deployment.yaml"
kubectl apply -f "${MANIFESTS_DIR}/service.yaml"

echo ""
echo "==> Waiting for rollout..."
kubectl -n golem-system rollout status deployment/golem-control-plane

echo ""
echo "==> Done. Pod status:"
kubectl -n golem-system get pods

echo ""
echo "==> To access the service, run in a separate terminal:"
echo "    kubectl -n golem-system port-forward svc/golem-control-plane 9000:9000"
