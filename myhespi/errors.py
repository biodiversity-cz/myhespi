from __future__ import annotations

from functools import wraps


def handle_errors(error_handler):
    """Decorator that delegates any unhandled exception to *error_handler(exc)*."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except Exception as exc:
                return error_handler(exc)

        return wrapper

    return decorator
