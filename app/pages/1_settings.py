from __future__ import annotations

from typing import Any, Dict, List, Tuple

import streamlit as st

from app.core.config import load_servers, load_settings, save_servers, save_settings
from app.core.models import AppSettings, MCPServer
from app.core.ollama import OllamaError, get_version, list_models

st.set_page_config(
    page_title="Settings", initial_sidebar_state="collapsed", layout="centered"
)


@st.cache_data(show_spinner=False)
def _cached_models(endpoint: str) -> List[Dict[str, Any]]:
    models = list_models(endpoint)
    return [model.model_dump() for model in models]


def _thinking_label_from_value(value: Any) -> str:
    value_map = {
        None: "Disabled",
        False: "Disabled",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        True: "Enabled (auto)",
    }
    normalized = str(value).strip().lower() if isinstance(value, str) else value
    return value_map.get(normalized, "Enabled (auto)" if value else "Disabled")


def _thinking_value_from_label(label: str) -> Any:
    mapping = {
        "Disabled": None,
        "Low": "low",
        "Medium": "medium",
        "High": "high",
        "Enabled (auto)": True,
    }
    return mapping.get(label, None)


def _sync_widget_defaults(settings: AppSettings) -> None:
    signature = settings.model_dump()
    if st.session_state.get("settings_signature") == signature:
        return
    st.session_state["settings_signature"] = signature
    st.session_state["settings_endpoint_value"] = settings.ollama_endpoint
    st.session_state["settings_model_value"] = settings.ollama_model
    st.session_state["settings_thinking_choice"] = _thinking_label_from_value(
        settings.thinking_level
    )
    st.session_state["settings_show_thoughts_value"] = settings.show_thoughts
    st.session_state["settings_streaming_value"] = settings.enable_streaming
    st.session_state.setdefault("new_server_enabled", True)


def _build_model_options(endpoint: str) -> Tuple[List[str], str | None]:
    try:
        models = _cached_models(endpoint)
    except OllamaError as exc:
        return [], str(exc)
    return [entry["name"] for entry in models], None


settings = load_settings()
servers = load_servers()
st.session_state["app_settings"] = settings
st.session_state["app_servers"] = servers
_sync_widget_defaults(settings)

tabs = st.tabs(["Assistant Defaults", "MCP Servers"])


with tabs[0]:
    st.subheader("Assistant Defaults")

    endpoint_value = st.text_input("Ollama endpoint", key="settings_endpoint_value")

    refresh_models_clicked = st.button(
        "Refresh available models", help="Fetch the latest models from Ollama."
    )
    if refresh_models_clicked:
        _cached_models.clear()  # type: ignore[attr-defined]

    model_options, model_error = _build_model_options(endpoint_value)
    if not model_options and st.session_state["settings_model_value"]:
        model_options = [st.session_state["settings_model_value"]]

    if st.session_state["settings_model_value"] not in model_options and model_options:
        st.session_state["settings_model_value"] = model_options[0]

    selected_model = st.selectbox(
        "Default model",
        model_options or ["No models available"],
        key="settings_model_value",
    )

    if model_error:
        st.warning(f"Could not fetch models: {model_error}")
    elif not model_options:
        st.info(
            "No models detected. Make sure Ollama is running and has models pulled."
        )

    thinking_choice = st.selectbox(
        "Thinking level",
        ["Disabled", "Low", "Medium", "High", "Enabled (auto)"],
        key="settings_thinking_choice",
        help="Enable thinking output for compatible models.",
    )

    show_thoughts = st.toggle(
        "Show thinking output in chat",
        key="settings_show_thoughts_value",
    )
    streaming = st.toggle(
        "Stream assistant responses",
        key="settings_streaming_value",
    )

    version = get_version(endpoint_value)
    if version:
        st.success(f"Ollama reachable (v{version})")
    else:
        st.caption("Unable to verify Ollama at the configured endpoint.")

    if st.button("Save settings", type="primary"):
        updated = AppSettings(
            ollama_endpoint=endpoint_value,
            ollama_model=selected_model,
            thinking_level=_thinking_value_from_label(thinking_choice),
            show_thoughts=show_thoughts,
            enable_streaming=streaming,
        )
        save_settings(updated)
        st.session_state["app_settings"] = updated
        _sync_widget_defaults(updated)
        st.success("Settings saved.")


with tabs[1]:
    st.subheader("MCP Servers")

    if not servers:
        st.info("No MCP servers configured yet.")

    for idx, server in enumerate(servers):
        with st.expander(f"{server.name}", expanded=False):
            with st.form(f"server_form_{idx}"):
                col1, col2 = st.columns(2)
                name_value = col1.text_input(
                    "Name", value=server.name, key=f"server_name_{idx}"
                )
                url_value = col2.text_input(
                    "Base URL", value=server.url, key=f"server_url_{idx}"
                )
                enabled_value = st.toggle(
                    "Enabled", value=server.enabled, key=f"server_enabled_{idx}"
                )
                save_col, delete_col = st.columns(2)
                save_clicked = save_col.form_submit_button(
                    "Save changes", type="primary", use_container_width=True
                )
                delete_clicked = delete_col.form_submit_button(
                    "Delete", type="secondary", use_container_width=True
                )

                if save_clicked:
                    servers[idx] = MCPServer(
                        name=name_value,
                        url=url_value,
                        enabled=enabled_value,
                    )
                    save_servers(servers)
                    st.session_state["app_servers"] = servers
                    st.success(f"Updated server `{name_value}`.")

                if delete_clicked:
                    updated_servers = [s for s in servers if s.name != server.name]
                    save_servers(updated_servers)
                    st.session_state["app_servers"] = updated_servers
                    st.warning(f"Deleted server `{server.name}`.")
                    st.rerun()

    st.divider()
    st.write("Add a new MCP server")
    with st.form("add_server_form", clear_on_submit=False):
        new_name = st.text_input("Server name", key="new_server_name")
        new_url = st.text_input("Server URL", key="new_server_url")
        new_enabled = st.toggle("Enabled", key="new_server_enabled")
        add_clicked = st.form_submit_button("Add server")

        if add_clicked:
            if not new_name or not new_url:
                st.error("Name and URL are required.")
            elif any(s.name == new_name for s in servers):
                st.error("A server with that name already exists.")
            else:
                new_server = MCPServer(
                    name=new_name,
                    url=new_url,
                    enabled=new_enabled,
                )
                updated_servers = servers + [new_server]
                save_servers(updated_servers)
                st.session_state["app_servers"] = updated_servers
                st.success(f"Added `{new_name}`.")
                st.session_state["new_server_name"] = ""
                st.session_state["new_server_url"] = ""
                st.session_state["new_server_enabled"] = True
                st.rerun()
