#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Delete the Golem Control Plane image from the local Minikube cluster.
#
# Usage:
#   ./minikube/delete_images.sh [TAG]
#
# Examples:
#   ./minikube/delete_images.sh        # deletes localhost/golem-control-plane:v1
#   ./minikube/delete_images.sh v2     # deletes localhost/golem-control-plane:v2
# -----------------------------------------------------------------------------

set -euo pipefail

TAG="${1:-v1}"
IMAGE="localhost/golem-control-plane:${TAG}"

if minikube status &>/dev/null; then
    echo "==> Deleting image from Minikube: ${IMAGE}"
    minikube image rm "${IMAGE}" 2>/dev/null || echo "Minikube image ${IMAGE} not found or could not be deleted."
else
    echo "WARN: Minikube is not running, skipping Minikube image deletion."
fi

echo ""
echo "==> Done."
