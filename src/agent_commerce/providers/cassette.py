"""Replay a frozen model transcript.

Adapted from the public agent-runtime-evals cassette. CI uses this so a test
never calls a paid API. The runtime, the merchant, and the mandate checks
still run. Only the model turn is played back. See docs/PROVENANCE.md.
"""

from __future__ import annotations

from agent_commerce.errors import PermanentError
from agent_commerce.providers.types import Completion, CompletionRequest


class CassetteProvider:
    name = "cassette"

    def __init__(self, completions: tuple[Completion, ...]) -> None:
        self._completions = completions
        self._index = 0

    def complete(self, request: CompletionRequest) -> Completion:
        # The request is ignored on purpose. Tokens were frozen at record time.
        del request
        if self._index >= len(self._completions):
            raise PermanentError("cassette exhausted")
        completion = self._completions[self._index]
        self._index += 1
        return completion
