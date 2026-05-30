# server/session.py
"""
Session state for the Skill Graph MCP server.

stdio transport (local): module-level singleton tracks state across the
lifetime of the single process = single session.

HTTP/Streamable-HTTP transport (Vercel): each tool call is a separate
stateless HTTP request, so per-request fresh state is returned instead.
The VERCEL env var (set automatically by Vercel) triggers this behaviour.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

GET_SKILL_RATE_LIMIT: int = 10
ACTIVE_TOOL_CAP: int = 15

_IS_HTTP: bool = bool(
    os.getenv("VERCEL")
    or os.getenv("MCP_TRANSPORT", "").lower() in ("sse", "streamable-http")
)


@dataclass
class SessionState:
    """Tracks per-session usage for the MCP server."""

    get_skill_calls: int = 0
    visited_nodes: set[str] = field(default_factory=set)
    active_tools: list[str] = field(default_factory=list)


_state: SessionState = SessionState()


def get_state() -> SessionState:
    """
    Return session state.

    Under stdio: returns the persistent module-level singleton.
    Under HTTP: returns a fresh instance per call (stateless behaviour).
    """
    if _IS_HTTP:
        return SessionState()
    return _state


def reset_state() -> None:
    """Reset state to defaults. Intended for use in tests only."""
    global _state
    _state = SessionState()
