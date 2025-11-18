from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.models import MCPServer, ToolBinding


class MCPClientError(RuntimeError):
    """Raised when an MCP server interaction fails."""


class ToolInvocationError(MCPClientError):
    """Raised when invoking a tool fails."""


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0, read=30.0)


def fetch_server_tools(server: MCPServer) -> List[ToolBinding]:
    """Fetch the tool manifest for a single server."""
    url = f"{server.base_url}/tools"
    try:
        response = httpx.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MCPClientError(f"{server.name}: unable to fetch tools ({exc})") from exc

    tool_payload = response.json()
    bindings: List[ToolBinding] = []
    for entry in tool_payload:
        entry_name = entry.get("name") or "tool"
        unique_name = f"{server.name}-{entry_name}"
        definition = {
            "type": "function",
            "function": {
                "name": unique_name,
                "description": entry.get("description", ""),
                "parameters": entry.get("parameters")
                or {"type": "object", "properties": {}},
            },
        }
        bindings.append(
            ToolBinding(
                name=unique_name,
                display_name=entry_name,
                server_name=server.name,
                definition=definition,
                endpoint=f"{server.base_url}/tools/{entry_name}",
                method=str(entry.get("method", "POST")).upper(),
            )
        )
    return bindings


def refresh_tool_bindings(
    servers: List[MCPServer],
) -> Tuple[List[ToolBinding], List[str]]:
    """Fetch tools for all enabled servers, collecting any failures."""
    bindings: List[ToolBinding] = []
    errors: List[str] = []
    for server in servers:
        if not server.enabled:
            continue
        try:
            bindings.extend(fetch_server_tools(server))
        except MCPClientError as exc:
            errors.append(str(exc))
    return bindings, errors


def call_tool(
    binding: ToolBinding,
    arguments: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Invoke a tool based on its binding metadata."""
    request_headers = headers.copy() if headers else None
    try:
        if binding.method == "GET":
            response = httpx.get(
                binding.endpoint,
                params=arguments,
                timeout=DEFAULT_TIMEOUT,
                headers=request_headers,
            )
        else:
            response = httpx.post(
                binding.endpoint,
                json=arguments,
                timeout=DEFAULT_TIMEOUT,
                headers=request_headers,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ToolInvocationError(f"{binding.name} failed: {exc}") from exc

    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text
