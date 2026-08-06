# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""HTTP tool: perform GET health checks against external URLs."""

import httpx
from langchain_core.tools import tool


@tool
def http_health_check(url: str) -> str:
    """Perform an HTTP GET request to the given URL and return its status."""
    try:
        response = httpx.get(url, timeout=5.0)
        return f"Status Code: {response.status_code} | Body: {response.text[:200]}"
    except Exception as e:
        return f"Error connecting to {url}: {e}"
