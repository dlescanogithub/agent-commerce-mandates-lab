"""Model turn types. Tool arguments are JSON objects, not free text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class Completion:
    content: str
    tool_calls: tuple[ToolCall, ...]
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class CompletionRequest:
    messages: tuple[dict[str, object], ...]
