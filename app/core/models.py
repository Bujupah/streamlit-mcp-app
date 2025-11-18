from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class AppSettings(BaseModel):
    """Application-wide configuration for the assistant."""

    ollama_endpoint: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3")
    thinking_level: Union[str, bool, None] = Field(default=None)
    show_thoughts: bool = Field(default=False)
    enable_streaming: bool = Field(default=True)

    @field_validator("ollama_endpoint", mode="before")
    @classmethod
    def _strip_endpoint(cls, value: str) -> str:
        if not value:
            return "http://localhost:11434"
        return value.rstrip("/")

    @property
    def think_argument(self) -> Union[str, bool, None]:
        """Return the value to send to Ollama's `think` parameter."""
        value = self.thinking_level
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if not normalized or normalized in {"none", "off", "disabled"}:
            return None
        if normalized in {"low", "medium", "high"}:
            return normalized
        if normalized in {"true", "yes", "on"}:
            return True
        return normalized


class MCPServer(BaseModel):
    """Definition of an MCP server."""

    name: str
    url: str
    enabled: bool = Field(default=True)
    description: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        if not value:
            return value
        return value.rstrip("/")

    @property
    def base_url(self) -> str:
        return self.url


class ToolBinding(BaseModel):
    """Tracks metadata for tools exposed to Ollama (and how to invoke them)."""

    name: str
    display_name: str
    server_name: str
    definition: Dict[str, Any]
    endpoint: str
    method: Literal["GET", "POST"] = "POST"

    def as_ollama_tool(self) -> Dict[str, Any]:
        return self.definition


class ModelSummary(BaseModel):
    name: str
    parameter_size: Optional[str] = None
    family: Optional[str] = None
    quantization_level: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, payload: Dict[str, Any]) -> "ModelSummary":
        details = payload.get("details") or {}
        return cls(
            name=payload.get("name", ""),
            parameter_size=details.get("parameter_size"),
            family=details.get("family"),
            quantization_level=details.get("quantization_level"),
            tags=payload,
        )
