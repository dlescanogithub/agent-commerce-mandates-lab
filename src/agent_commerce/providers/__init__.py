"""Model adapters. The default is the local stub. Live eval is opt-in."""

from agent_commerce.providers.cassette import CassetteProvider
from agent_commerce.providers.fake import FakeProvider

__all__ = ["CassetteProvider", "FakeProvider"]
