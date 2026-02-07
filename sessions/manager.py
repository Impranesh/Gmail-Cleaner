"""
Session management - in-memory session store for user sessions.
"""
from typing import Dict, Any
import secrets

_sessions: Dict[str, Dict[str, Any]] = {}


def create_session(queries: list, restore_enabled: bool) -> str:
    """Create a new session and return session ID."""
    session_id = secrets.token_hex(16)
    _sessions[session_id] = {
        "queries": queries,
        "restore_enabled": restore_enabled,
        "state": None,
        "creds": None
    }
    return session_id


def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieve session by ID."""
    return _sessions.get(session_id)


def update_session(session_id: str, data: Dict[str, Any]) -> None:
    """Update session data."""
    if session_id in _sessions:
        _sessions[session_id].update(data)


def delete_session(session_id: str) -> None:
    """Delete a session."""
    if session_id in _sessions:
        del _sessions[session_id]


def list_all_sessions() -> Dict[str, Dict[str, Any]]:
    """List all active sessions (for debugging)."""
    return _sessions
