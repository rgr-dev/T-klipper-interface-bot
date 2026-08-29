"""Simple token-based authentication for the REST API.

This is a mechanism separate from the Telegram allowlist (username/user_id
don't apply to an HTTP client): a single shared token, meant for personal
use (own apps, scripts, dashboards) — not for multiple users with roles.
If something more granular is needed, this can be revisited in the future.
"""
from __future__ import annotations

import os
from functools import wraps

from quart import request

REST_API_TOKEN_ENV = "REST_API_TOKEN"


def require_api_token(view):
    @wraps(view)
    async def wrapped(*args, **kwargs):
        expected = os.environ.get(REST_API_TOKEN_ENV)
        if not expected:
            # No token configured, the API is disabled for security.
            return {"error": "REST API disabled: REST_API_TOKEN is missing"}, 503

        provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if provided != expected:
            return {"error": "Unauthorized"}, 401

        return await view(*args, **kwargs)

    return wrapped
