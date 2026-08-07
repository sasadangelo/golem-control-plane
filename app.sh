#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Start the Golem Control Plane.
#
# Usage (local dev):
#   ./app.sh
#
# The script resolves the source directory relative to its own location so it
# can be invoked from any working directory.
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src/golem-control-plane"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9000}"
WORKERS="${WORKERS:-1}"

# Use the venv uvicorn in local dev; fall back to the system uvicorn inside Docker.
VENV_UVICORN="${SCRIPT_DIR}/.venv/bin/uvicorn"
if [[ -x "${VENV_UVICORN}" ]]; then
  UVICORN="${VENV_UVICORN}"
elif command -v uvicorn &>/dev/null; then
  UVICORN="uvicorn"
else
  echo "ERROR: uvicorn not found. Run: uv sync --extra dev" >&2
  exit 1
fi

exec "${UVICORN}" interfaces.api.app:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --app-dir "${SRC_DIR}"
