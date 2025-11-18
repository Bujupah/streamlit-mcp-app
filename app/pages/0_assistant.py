from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.core.config import load_servers, load_settings, set_server_enabled
from app.core.models import AppSettings, MCPServer, ToolBinding
from app.core.ollama import OllamaError, chat_completion, list_models, stream_chat
from app.mcp.client import ToolInvocationError, call_tool, refresh_tool_bindings

st.set_page_config(page_title="Assistant", layout="wide")

STATE_SETTINGS = "app_settings"
STATE_SERVERS = "app_servers"
STATE_MESSAGES = "chat_messages"
STATE_MODELS = "ollama_models"
STATE_MODEL_ERROR = "ollama_model_error"
STATE_SELECTED_MODEL = "selected_model"
STATE_TOOL_BINDINGS = "tool_bindings"
STATE_TOOL_LOOKUP = "tool_lookup"
STATE_TOOL_ERRORS = "tool_errors"
STATE_GENERATING = "assistant_generating"
STATE_REQUEST_STATUS = "request_status"

STATUS_LOADING = "Loading..."
STATUS_THINKING = "Thinking..."
STATUS_PROCESSING = "Processing..."
STATUS_THOUGHTS = "Thoughts..."
STATUS_ERROR = "Error"

logger = logging.getLogger("assistant_page")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [assistant]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_step(message: str, **context: Any) -> None:
    if context:
        context_str = " ".join(
            f"{key}={value!r}" for key, value in sorted(context.items())
        )
        logger.info("%s | %s", message, context_str)
    else:
        logger.info(message)


def _get_request_status(default: str = STATUS_THOUGHTS) -> str:
    return st.session_state.get(STATE_REQUEST_STATUS, default)


def _set_request_status(status: str) -> None:
    previous = st.session_state.get(STATE_REQUEST_STATUS)
    st.session_state[STATE_REQUEST_STATUS] = status
    if previous != status:
        log_step("Request status updated", previous=previous, status=status)


def _update_runtime_settings(**updates: Any) -> AppSettings:
    """Apply in-session updates to assistant runtime settings."""
    if not updates:
        return st.session_state[STATE_SETTINGS]
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    new_settings = settings.model_copy(update=updates)
    st.session_state[STATE_SETTINGS] = new_settings
    log_step("Runtime settings updated", **updates)
    return new_settings


class RequestStatusView:
    """Renders and updates the per-request status (and thinking output)."""

    def __init__(self, *, show_thoughts: bool):
        self.show_thoughts = show_thoughts
        self.status = _get_request_status(STATUS_THOUGHTS)
        self.thinking_placeholder = st.empty() if show_thoughts else None
        self.thinking_text = ""
        self.placeholder_message = "_Thinking..._"
        self._render_thinking()

    def _render_thinking(self) -> None:
        if not self.thinking_placeholder:
            return
        self.thinking_placeholder.empty()
        with self.thinking_placeholder.container():
            with st.expander(self.status or STATUS_THOUGHTS, icon="💭"):
                if self.thinking_text:
                    st.code(
                        self.thinking_text,
                        language="markdown",
                        line_numbers=False,
                        wrap_lines=True,
                    )
                else:
                    st.caption(self.placeholder_message)

    def update_status(self, status: str) -> None:
        self.status = status or STATUS_THOUGHTS
        _set_request_status(self.status)
        self._render_thinking()

    def update_thinking(self, text: str) -> None:
        self.thinking_text = text
        self._render_thinking()

    def show_placeholder(self, message: str) -> None:
        self.placeholder_message = message
        if not self.thinking_text:
            self._render_thinking()


@st.cache_data(show_spinner=False)
def _cached_model_list(endpoint: str) -> List[Dict[str, Any]]:
    models = list_models(endpoint)
    return [model.model_dump() for model in models]


def _init_state() -> None:
    log_step("Initializing session state")
    st.session_state[STATE_SETTINGS] = load_settings()
    st.session_state[STATE_SERVERS] = load_servers()
    st.session_state.setdefault(STATE_MESSAGES, [])
    st.session_state.setdefault(STATE_MODELS, [])
    st.session_state.setdefault(STATE_MODEL_ERROR, None)
    st.session_state.setdefault(
        STATE_SELECTED_MODEL, st.session_state[STATE_SETTINGS].ollama_model
    )
    st.session_state.setdefault(STATE_TOOL_BINDINGS, [])
    st.session_state.setdefault(STATE_TOOL_LOOKUP, {})
    st.session_state.setdefault(STATE_TOOL_ERRORS, [])
    st.session_state.setdefault(STATE_GENERATING, False)
    st.session_state.setdefault(STATE_REQUEST_STATUS, STATUS_THOUGHTS)
    log_step(
        "Session state initialized",
        servers=len(st.session_state[STATE_SERVERS]),
        messages=len(st.session_state[STATE_MESSAGES]),
    )


def _refresh_models() -> None:
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    log_step("Refreshing models", endpoint=settings.ollama_endpoint)
    try:
        model_payload = _cached_model_list(settings.ollama_endpoint)
        st.session_state[STATE_MODELS] = model_payload
        st.session_state[STATE_MODEL_ERROR] = None
        log_step("Models refreshed", count=len(model_payload))
    except OllamaError as exc:
        st.session_state[STATE_MODELS] = []
        st.session_state[STATE_MODEL_ERROR] = str(exc)
        log_step("Model refresh failed", error=str(exc))


def _refresh_tools() -> None:
    servers: List[MCPServer] = st.session_state[STATE_SERVERS]
    log_step("Refreshing tools", servers=len(servers))
    bindings, errors = refresh_tool_bindings(servers)
    st.session_state[STATE_TOOL_BINDINGS] = bindings
    st.session_state[STATE_TOOL_LOOKUP] = {
        binding.name: binding for binding in bindings
    }
    st.session_state[STATE_TOOL_ERRORS] = errors
    log_step(
        "Tool refresh complete",
        bindings=len(bindings),
        errors=len(errors),
    )


def _on_server_toggle(server_name: str) -> None:
    enabled = st.session_state.get(f"server_toggle_{server_name}", False)
    servers = set_server_enabled(server_name, enabled)
    st.session_state[STATE_SERVERS] = servers
    log_step("Server toggled", server=server_name, enabled=enabled)


def _clear_chat() -> None:
    log_step("Clearing conversation history")
    st.session_state[STATE_MESSAGES] = []
    _set_request_status(STATUS_THOUGHTS)
    st.toast("Conversation cleared.")


def _render_messages(show_thoughts: bool) -> None:
    messages = st.session_state[STATE_MESSAGES]
    if not messages:
        st.info("Ask me something to start the conversation.")
        return
    idx = 0
    while idx < len(messages):
        message = messages[idx]
        role = message.get("role")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(message.get("content", ""), unsafe_allow_html=True)
            idx += 1
            continue
        if role == "assistant":
            inline_tools: List[Dict[str, Any]] = []
            scan_idx = idx + 1
            while scan_idx < len(messages) and messages[scan_idx].get("role") == "tool":
                inline_tools.append(messages[scan_idx])
                scan_idx += 1
            with st.chat_message("assistant"):
                if show_thoughts and message.get("thinking"):
                    expander_label = message.get("status") or "Thinking"
                    with st.expander(expander_label):
                        st.code(
                            message.get("thinking", ""),
                            language="markdown",
                            line_numbers=False,
                            wrap_lines=True,
                        )
                content = message.get("content") or ""
                awaiting_tool_results = not content and (
                    inline_tools or message.get("tool_calls")
                )
                if content:
                    st.markdown(content, unsafe_allow_html=True)
                elif awaiting_tool_results:
                    st.markdown("_Awaiting tool results..._")
                else:
                    st.caption("_No assistant response text_")
                if inline_tools:
                    for tool_message in inline_tools:
                        tool_name = tool_message.get("name") or "tool"
                        st.markdown(f"**Result from `{tool_name}`**")
                        st.code(
                            tool_message.get("content", ""),
                            language="json",
                            wrap_lines=True,
                        )
                status_text = message.get("status")
                if status_text:
                    st.caption(f"Status: {status_text}")
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    tool_names = ", ".join(
                        call.get("function", {}).get("name", "tool")
                        for call in tool_calls
                    )
                    st.caption(f"Tool calls requested: {tool_names}")
            idx = scan_idx
            continue
        if role == "tool":
            tool_name = message.get("name") or "tool"
            with st.chat_message("assistant", avatar="🛠️"):
                st.markdown(f"**Result from `{tool_name}`**")
                st.code(message.get("content", ""), language="json", wrap_lines=True)
            idx += 1
            continue
        idx += 1


def _prepare_payload() -> Dict[str, Any]:
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    payload: Dict[str, Any] = {
        "model": st.session_state.get(STATE_SELECTED_MODEL, settings.ollama_model),
        "messages": st.session_state[STATE_MESSAGES],
    }
    think_arg = settings.think_argument
    if think_arg is not None:
        payload["think"] = think_arg
    bindings: List[ToolBinding] = st.session_state[STATE_TOOL_BINDINGS]
    if bindings:
        payload["tools"] = [binding.as_ollama_tool() for binding in bindings]
    log_step(
        "Prepared payload",
        model=payload["model"],
        messages=len(payload["messages"]),
        tools=len(payload.get("tools", [])),
        thinking=think_arg is not None,
    )
    return payload


def _consume_stream(payload: Dict[str, Any], show_thoughts: bool):
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    aggregated = {"role": "assistant", "content": "", "thinking": "", "tool_calls": []}
    final_event: Dict[str, Any] = {}
    status_view: Optional[RequestStatusView] = None
    with st.chat_message("assistant"):
        status_view = RequestStatusView(show_thoughts=show_thoughts)
        tool_box = st.container()
        content_box = st.empty()
        try:
            status_view.update_status(STATUS_THINKING)
            log_step(
                "Streaming chat response",
                model=payload.get("model"),
                messages=len(payload.get("messages", [])),
            )
            for event in stream_chat(settings.ollama_endpoint, payload):
                final_event = event
                message = event.get("message") or {}
                if message.get("content"):
                    aggregated["content"] += message["content"]
                    content_box.markdown(aggregated["content"], unsafe_allow_html=True)
                if show_thoughts and message.get("thinking"):
                    aggregated["thinking"] += message["thinking"]
                    status_view.update_thinking(aggregated["thinking"])
                if message.get("tool_calls"):
                    aggregated["tool_calls"] = message["tool_calls"]
                    status_view.update_status(STATUS_PROCESSING)
                    log_step(
                        "Tool calls requested during stream",
                        tools=[
                            call.get("function", {}).get("name", "tool")
                            for call in aggregated["tool_calls"]
                        ],
                    )
                    tool_names = ", ".join(
                        call.get("function", {}).get("name", "tool")
                        for call in aggregated["tool_calls"]
                    )
                    tool_box.caption(f"Tool calls requested: {tool_names}")
            if not aggregated["content"] and aggregated["tool_calls"]:
                content_box.markdown("_Awaiting tool results..._")
            if show_thoughts and not aggregated["thinking"]:
                status_view.show_placeholder("_No thinking output returned._")
            if not aggregated["tool_calls"]:
                status_view.update_status(STATUS_THOUGHTS)
            log_step(
                "Streaming response completed",
                content_len=len(aggregated["content"]),
                thinking_len=len(aggregated["thinking"]),
                tool_calls=len(aggregated.get("tool_calls") or []),
            )
        except OllamaError as exc:
            if status_view:
                status_view.update_status(STATUS_ERROR)
            st.error(f"Ollama error: {exc}")
            log_step("Streaming failed", error=str(exc))
            return None, tool_box, status_view
    response = {"message": aggregated}
    response.update(
        {key: value for key, value in final_event.items() if key != "message"}
    )
    return response, tool_box, status_view


def _run_completion(payload: Dict[str, Any], show_thoughts: bool):
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    status_view: Optional[RequestStatusView] = None
    with st.chat_message("assistant"):
        status_view = RequestStatusView(show_thoughts=show_thoughts)
        tool_box = st.container()
        content_box = st.empty()
        try:
            status_view.update_status(STATUS_THINKING)
            log_step(
                "Running chat completion",
                model=payload.get("model"),
                messages=len(payload.get("messages", [])),
            )
            response = chat_completion(settings.ollama_endpoint, payload)
        except OllamaError as exc:
            if status_view:
                status_view.update_status(STATUS_ERROR)
            st.error(f"Ollama error: {exc}")
            log_step("Chat completion failed", error=str(exc))
            return None, tool_box, status_view
        message = response.get("message") or {}
        if message.get("content"):
            content_box.markdown(message["content"], unsafe_allow_html=True)
        if show_thoughts and message.get("thinking"):
            status_view.update_thinking(message["thinking"])
        if show_thoughts and not message.get("thinking"):
            status_view.show_placeholder("_No thinking output returned._")
        if not message.get("content") and message.get("tool_calls"):
            content_box.markdown("_Awaiting tool results..._")
        if message.get("tool_calls"):
            status_view.update_status(STATUS_PROCESSING)
            tool_names = ", ".join(
                call.get("function", {}).get("name", "tool")
                for call in message["tool_calls"]
            )
            tool_box.caption(f"Tool calls requested: {tool_names}")
        else:
            status_view.update_status(STATUS_THOUGHTS)
        log_step(
            "Chat completion received",
            content_len=len(message.get("content") or ""),
            thinking_len=len(message.get("thinking") or ""),
            tool_calls=len(message.get("tool_calls") or []),
        )
        return response, tool_box, status_view


def _format_tool_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2)
    return str(result)


def _parse_arguments(raw_args: Any) -> Dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args)
        except json.JSONDecodeError:
            return {"value": raw_args}
    return {}


def _handle_tool_calls(
    tool_calls: List[Dict[str, Any]],
    *,
    tool_box: Optional[DeltaGenerator] = None,
    status_view: Optional[RequestStatusView] = None,
) -> None:
    lookup: Dict[str, ToolBinding] = st.session_state[STATE_TOOL_LOOKUP]
    for call in tool_calls:
        function_data = call.get("function") or {}
        tool_name = function_data.get("name", "")
        binding = lookup.get(tool_name)
        arguments = _parse_arguments(function_data.get("arguments"))
        if not binding:
            error_text = f"Tool `{tool_name}` is not available."
            st.warning(error_text)
            st.session_state[STATE_MESSAGES].append(
                {"role": "tool", "name": tool_name, "content": error_text}
            )
            if status_view:
                status_view.update_status(STATUS_ERROR)
            else:
                _set_request_status(STATUS_ERROR)
            log_step("Tool binding missing", tool=tool_name)
            continue
        try:
            if status_view:
                status_view.update_status(STATUS_PROCESSING)
            else:
                _set_request_status(STATUS_PROCESSING)
            log_step(
                "Invoking tool",
                tool=binding.name,
                server=binding.server_name,
                arguments=arguments,
            )
            result = call_tool(binding, arguments)
            rendered = _format_tool_result(result)
            log_step("Tool invocation succeeded", tool=binding.name)
        except ToolInvocationError as exc:
            rendered = f"Tool invocation failed: {exc}"
            if status_view:
                status_view.update_status(STATUS_ERROR)
            else:
                _set_request_status(STATUS_ERROR)
            log_step("Tool invocation failed", tool=binding.name, error=str(exc))
        st.session_state[STATE_MESSAGES].append(
            {"role": "tool", "name": binding.name, "content": rendered}
        )
        if tool_box is not None:
            tool_box.markdown(f"**{binding.server_name} · {binding.display_name}**")
            tool_box.code(rendered, language="json", wrap_lines=True)
        else:
            with st.chat_message("assistant", avatar="🛠️"):
                st.markdown(f"**{binding.server_name} · {binding.display_name}**")
                st.code(rendered, language="json", wrap_lines=True)


def _run_assistant_turn() -> None:
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    max_iterations = 3
    log_step("Starting assistant turn", max_iterations=max_iterations)
    for iteration in range(max_iterations):
        log_step("Assistant iteration started", iteration=iteration + 1)
        payload = _prepare_payload()
        _set_request_status(STATUS_LOADING)
        if settings.enable_streaming:
            response, tool_box, status_view = _consume_stream(
                payload, settings.show_thoughts
            )
        else:
            response, tool_box, status_view = _run_completion(
                payload, settings.show_thoughts
            )
        if not response:
            log_step("Assistant iteration failed", iteration=iteration + 1)
            break
        message = response.get("message") or {}
        status_value = (
            status_view.status if status_view else _get_request_status(STATUS_THOUGHTS)
        )
        assistant_message = {
            "role": "assistant",
            "content": message.get("content") or "",
            "status": status_value,
        }
        if message.get("thinking"):
            assistant_message["thinking"] = message["thinking"]
        if message.get("tool_calls"):
            assistant_message["tool_calls"] = message["tool_calls"]
        st.session_state[STATE_MESSAGES].append(assistant_message)
        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            _set_request_status(STATUS_THOUGHTS)
            if status_view and status_view.status != STATUS_THOUGHTS:
                status_view.update_status(STATUS_THOUGHTS)
            log_step(
                "Assistant turn finished",
                iteration=iteration + 1,
                reason="no_tool_calls",
            )
            break
        _set_request_status(STATUS_PROCESSING)
        if status_view:
            status_view.update_status(STATUS_PROCESSING)
        _handle_tool_calls(tool_calls, tool_box=tool_box, status_view=status_view)
        if status_view:
            assistant_message["status"] = status_view.status
        log_step(
            "Tool calls handled", iteration=iteration + 1, tool_calls=len(tool_calls)
        )
    else:
        log_step("Assistant turn reached max iterations", iterations=max_iterations)


def _handle_prompt(prompt: str) -> None:
    if not prompt:
        return
    preview = prompt.strip().replace("\n", " ")
    log_step(
        "Handling user prompt",
        length=len(prompt),
        preview=(preview[:80] + "…") if len(preview) > 80 else preview,
    )
    st.session_state[STATE_MESSAGES].append({"role": "user", "content": prompt})
    _set_request_status(STATUS_LOADING)
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state[STATE_GENERATING] = True
    try:
        _run_assistant_turn()
    finally:
        st.session_state[STATE_GENERATING] = False


def _render_sidebar() -> None:
    settings: AppSettings = st.session_state[STATE_SETTINGS]
    models = st.session_state[STATE_MODELS]
    if not models and st.session_state[STATE_MODEL_ERROR] is None:
        _refresh_models()
        models = st.session_state[STATE_MODELS]

    with st.sidebar:
        st.title("Assistant Console")

        col1, col2, col3 = st.columns(3, gap="small")
        if col1.button("New chat"):
            _clear_chat()
        if col2.button("Refresh tools"):
            _refresh_tools()
            st.toast("Tools refreshed")
        if col3.button("Refresh models"):
            _cached_model_list.clear()  # type: ignore[attr-defined]
            _refresh_models()
            st.toast("Models refreshed")

        model_error = st.session_state[STATE_MODEL_ERROR]
        model_options = [entry["name"] for entry in models] or [settings.ollama_model]
        if st.session_state[STATE_SELECTED_MODEL] not in model_options:
            st.session_state[STATE_SELECTED_MODEL] = model_options[0]
        selected_model = st.selectbox(
            "Model",
            model_options,
            index=model_options.index(st.session_state[STATE_SELECTED_MODEL]),
        )
        st.session_state[STATE_SELECTED_MODEL] = selected_model

        if model_error:
            st.warning(f"Ollama model list failed: {model_error}")

        st.subheader("MCP Servers")
        st.caption(
            "Enable/disable servers to control tool discovery. Refresh tools after changes."
        )
        for server in st.session_state[STATE_SERVERS]:
            key = f"server_toggle_{server.name}"
            st.session_state.setdefault(key, server.enabled)
            st.toggle(
                f"{server.name}",
                key=key,
                value=server.enabled,
                help=server.url,
                on_change=_on_server_toggle,
                args=(server.name,),
            )

        st.subheader("Tools")
        bindings: List[ToolBinding] = st.session_state[STATE_TOOL_BINDINGS]
        if not bindings:
            st.info(
                "No tools discovered yet. Click **Refresh tools** to fetch from servers."
            )
        else:
            st.markdown(
                "\n".join(
                    [
                        f"- <b>`{binding.name}`</b> <small>({binding.server_name})</small>"
                        for binding in bindings
                    ]
                ),
                unsafe_allow_html=True,
            )
        errors = st.session_state[STATE_TOOL_ERRORS]
        if errors:
            st.warning(
                "Tool discovery issues:\n" + "\n".join(f"- {err}" for err in errors)
            )

        st.subheader("Runtime")
        thinking_active = bool(settings.think_argument)
        thinking_toggle = st.toggle(
            "Enable thinking payload",
            value=thinking_active,
            key="runtime_toggle_thinking",
            help="Send the `think` argument to Ollama (requires reasoning-capable models).",
        )
        streaming_toggle = st.toggle(
            "Stream assistant responses",
            value=settings.enable_streaming,
            key="runtime_toggle_streaming",
        )
        show_thoughts_toggle = st.toggle(
            "Show thoughts in chat",
            value=settings.show_thoughts,
            key="runtime_toggle_show_thoughts",
        )
        st.caption(
            f"- Thinking payload: {'Enabled' if thinking_toggle else 'Disabled'}\n"
            f"- Streaming: {'Enabled' if streaming_toggle else 'Disabled'}\n"
            f"- Thoughts visible: {'Yes' if show_thoughts_toggle else 'No'}"
        )
        runtime_updates: Dict[str, Any] = {}
        if thinking_toggle != thinking_active:
            runtime_updates["thinking_level"] = True if thinking_toggle else None
        if streaming_toggle != settings.enable_streaming:
            runtime_updates["enable_streaming"] = streaming_toggle
        if show_thoughts_toggle != settings.show_thoughts:
            runtime_updates["show_thoughts"] = show_thoughts_toggle
        if runtime_updates:
            settings = _update_runtime_settings(**runtime_updates)
            st.toast("Runtime settings updated")


def main() -> None:
    _init_state()
    if (
        not st.session_state[STATE_TOOL_BINDINGS]
        and not st.session_state[STATE_TOOL_ERRORS]
    ):
        _refresh_tools()
    _render_sidebar()
    st.caption(
        f"Chatting as `{st.session_state[STATE_SELECTED_MODEL]}` · "
        f"{len(st.session_state[STATE_MESSAGES])} turns so far"
    )
    _render_messages(st.session_state[STATE_SETTINGS].show_thoughts)
    prompt = st.chat_input(
        "Ask anything...",
        disabled=st.session_state.get(STATE_GENERATING, False),
    )
    if prompt:
        _handle_prompt(prompt)


if __name__ == "__main__":
    main()
