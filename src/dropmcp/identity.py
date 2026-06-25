"""Resolve per-request user identity from trusted upstream headers."""

from __future__ import annotations


def resolve_user_email(header_name: str) -> str | None:
    """Return the caller identity from the configured HTTP header, if present."""
    try:
        from fastmcp.server.dependencies import get_http_request
    except Exception:
        return None

    try:
        request = get_http_request()
    except Exception:
        return None

    if request is None:
        return None

    headers = getattr(request, "headers", None)
    if headers is None:
        return None

    value = headers.get(header_name) if hasattr(headers, "get") else None
    if not value or not str(value).strip():
        return None
    return str(value).strip()


def user_from_request(request, header_name: str) -> str | None:
    """Extract user identity from a Starlette request."""
    value = request.headers.get(header_name)
    if not value or not value.strip():
        return None
    return value.strip()
