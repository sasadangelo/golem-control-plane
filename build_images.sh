#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Build the Golem Control Plane container image.
#
# Usage:
#   ./build_images.sh [TAG]
#
# Examples:
#   ./build_images.sh          # builds localhost/golem-control-plane:v1
#   ./build_images.sh v2       # builds localhost/golem-control-plane:v2
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${1:-v1}"
IMAGE="localhost/golem-control-plane:${TAG}"

echo "==> Building ${IMAGE}"
podman build -t "${IMAGE}" "${SCRIPT_DIR}"

echo ""
echo "==> Build complete: ${IMAGE}"
echo "    To load into Minikube run: ./minikube/load_images.sh ${TAG}"
