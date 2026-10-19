"""Errors the CLI and the eval gate can report without a stack trace."""


class CommerceError(Exception):
    """Base error. Callers catch this, not Exception, when they mean our code."""


class ConfigError(CommerceError):
    """The environment is missing a required setting or combines settings that conflict."""


class PermanentError(CommerceError):
    """A failure that will not change if the same call is repeated."""


class ValidationError(CommerceError):
    """A payload was not the shape the caller claimed."""
