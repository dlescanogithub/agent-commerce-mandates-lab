"""Provider surface. The cassette and the stub implement this. Live is optional."""

from __future__ import annotations

from typing import Protocol

from agent_commerce.providers.types import Completion, CompletionRequest


class LLMProvider(Protocol):
    name: str

    def complete(self, request: CompletionRequest) -> Completion: ...
