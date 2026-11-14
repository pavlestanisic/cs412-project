"""
Our own error types.

Having our own errors makes it easy to catch "app problems"
separately from real Python bugs.
"""


class DispatchError(Exception):
    """Base class for every error raised by this app."""


class ValidationError(DispatchError):
    """Raised when input data is wrong (empty name, negative price, ...)."""


class InvalidStateError(DispatchError):
    """Raised when an order action is not allowed in its current state."""


class NotFoundError(DispatchError):
    """Raised when something with the given id does not exist."""
