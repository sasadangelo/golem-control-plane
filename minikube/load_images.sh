#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Load the Golem Control Plane image into the local Minikube cluster.
#
# Usage:
#   ./minikube/load_images.sh [TAG]
#
# Examples:
#   ./minikube/load_images.sh            # loads localhost/golem-control-plane:v0.0.1
#   ./minikube/load_images.sh v0.0.2     # loads localhost/golem-control-plane:v0.0.2
#
# Prerequisites:
#   - Minikube must be running  (minikube status)
#   - Image must be built first (./build_images.sh)
# -----------------------------------------------------------------------------

set -euo pipefail

TAG="${1:-v0.0.1}"
IMAGE="localhost/golem-control-plane:${TAG}"
ARCHIVE="/tmp/golem-control-plane-${TAG}.tar"

echo "==> Saving ${IMAGE} to ${ARCHIVE}"
podman save "${IMAGE}" -o "${ARCHIVE}"

echo "==> Loading ${ARCHIVE} into Minikube"
minikube image load "${ARCHIVE}"

echo "==> Cleaning up ${ARCHIVE}"
rm -f "${ARCHIVE}"

echo ""
echo "==> Done. Verifying:"
minikube image ls | grep golem-control-plane || echo "WARN: image not found in minikube image ls"
