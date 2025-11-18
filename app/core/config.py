from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .models import AppSettings, MCPServer

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
SERVERS_PATH = CONFIG_DIR / "servers.json"

DEFAULT_SETTINGS = AppSettings()
DEFAULT_SERVERS = [MCPServer(name="dummy_server", url="http://localhost:3000")]


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> AppSettings:
    """Load persisted settings (or defaults)."""
    _ensure_config_dir()
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    return AppSettings(**payload)


def save_settings(settings: AppSettings) -> None:
    _ensure_config_dir()
    SETTINGS_PATH.write_text(
        settings.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )


def load_servers() -> List[MCPServer]:
    """Return all configured MCP servers."""
    _ensure_config_dir()
    if not SERVERS_PATH.exists():
        save_servers(DEFAULT_SERVERS)
        return DEFAULT_SERVERS
    try:
        raw_servers = json.loads(SERVERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        save_servers(DEFAULT_SERVERS)
        return DEFAULT_SERVERS
    servers: List[MCPServer] = []
    for entry in raw_servers:
        try:
            servers.append(MCPServer(**entry))
        except Exception:
            continue
    if not servers:
        servers = DEFAULT_SERVERS
    return servers


def save_servers(servers: Iterable[MCPServer]) -> None:
    _ensure_config_dir()
    SERVERS_PATH.write_text(
        json.dumps(
            [server.model_dump(exclude_none=True) for server in servers], indent=2
        ),
        encoding="utf-8",
    )


def set_server_enabled(server_name: str, enabled: bool) -> List[MCPServer]:
    """Toggle a server on/off and persist it."""
    servers = load_servers()
    updated = False
    for idx, server in enumerate(servers):
        if server.name == server_name:
            servers[idx] = server.model_copy(update={"enabled": enabled})
            updated = True
            break
    if updated:
        save_servers(servers)
    return servers


def remove_server(server_name: str) -> List[MCPServer]:
    """Remove a server (if it exists)."""
    servers = [server for server in load_servers() if server.name != server_name]
    save_servers(servers)
    return servers
