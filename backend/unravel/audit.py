"""Persistent audit log (Firestore) for clinician review and Fivetran observability.

Every consequential action, an agent verdict, a Fivetran write (re-sync, pause,
onboard), is appended to the `AuditLog` collection with a timestamp and category,
so the Audit trail survives across sessions (not just the in-browser session feed).
"""

from __future__ import annotations

import time

PROJECT = "unravel-ra"
_COLL = "AuditLog"


def _client(client=None):
    if client is not None:
        return client
    from google.cloud import firestore
    return firestore.Client(project=PROJECT)


def log(category: str, text: str, *, tone: str = "info", actor: str = "system", client=None) -> None:
    """Append one audit event. Best-effort: never block an action on logging."""
    try:
        from google.cloud import firestore
        _client(client).collection(_COLL).add({
            "category": category, "text": text, "tone": tone, "actor": actor,
            "ts": firestore.SERVER_TIMESTAMP, "ts_ms": int(time.time() * 1000),
        })
    except Exception:
        pass


def recent(limit: int = 100, *, client=None) -> list[dict]:
    """The most recent audit events, newest first."""
    try:
        from google.cloud import firestore
        q = (_client(client).collection(_COLL)
             .order_by("ts_ms", direction=firestore.Query.DESCENDING).limit(limit))
        return [{
            "category": r.get("category"), "text": r.get("text"),
            "tone": r.get("tone"), "actor": r.get("actor"), "ts_ms": r.get("ts_ms"),
        } for r in (d.to_dict() for d in q.stream())]
    except Exception:
        return []
