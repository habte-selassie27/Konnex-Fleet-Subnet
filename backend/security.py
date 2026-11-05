"""Request authentication helpers.

Status: COMPLETE (Phase 6) — X-Fleet-API-Key header check (AGENTS.md §2.8).
JWT is post-MVP.
"""

from fastapi import HTTPException, Request


def require_api_key(request: Request) -> None:
    """Reject requests without a valid X-Fleet-API-Key header."""
    settings = request.app.state.settings
    provided = request.headers.get("X-Fleet-API-Key")
    if provided != settings.fleet_api_key:
        raise HTTPException(status_code=401, detail="invalid or missing X-Fleet-API-Key")
