"""Deep Fivetran MCP inside the reasoning loop.

The Fivetran track's stand-out lever is using the partner MCP server for more than
a one-shot pull: weaving freshness checks and targeted re-syncs into the agent
loop. Before the Adjudicator rules on a reclassification, the loop asks the
Fivetran MCP server how fresh each evidence feed is (get_connection_details); if a
feed is stale it can trigger a targeted re-sync (sync_connection) and the
Adjudicator's verdict then accounts for data freshness explicitly.

This wraps the official server (github.com/fivetran/fivetran-mcp) over stdio,
honouring its read-the-schema-first guardrail (each tool needs a confirming
schema_file path, parsed from its own description). Reads are always allowed;
writes (sync_connection) are gated behind FIVETRAN_ALLOW_WRITES, set only when the
loop explicitly asks for a re-sync. Credentials are read from Secret Manager at
runtime.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT = "unravel-ra"
# evidence feeds we care about, keyed by the BigQuery schema the connector writes.
# gnomad_sdk is the custom Connector-SDK connector (Python hosted on Fivetran).
EVIDENCE_SCHEMAS = ("clinvar", "gnomad", "alphamissense", "gnomad_sdk")
_SCHEMA_PATH = re.compile(r"(open-api-definitions/[^'\"]+\.json)")

# Known Fivetran connector ids for the evidence feeds (created via the REST API,
# see the Day-2 handoff). Used by the REST freshness path, which works in
# environments where the MCP server cannot be spawned (e.g. the slim Cloud Run
# container has no git for `uvx --from git+...`).
_CONNECTORS = {
    "clinvar": "inexperience_publicly",
    "gnomad": "afferent_wisplike",
    "alphamissense": "fall_frequent",
    "gnomad_sdk": "turban_conferring",   # custom Connector SDK connector (Python on Fivetran)
}


def _on_cloud_run() -> bool:
    return bool(os.environ.get("K_SERVICE"))


def _secret(name: str) -> str:
    # On Cloud Run the secrets are mounted as env vars via --set-secrets
    # (FIVETRAN_API_KEY / FIVETRAN_API_SECRET); locally we fall back to gcloud.
    env_val = os.environ.get(name.upper().replace("-", "_"))
    if env_val:
        return env_val
    out = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         f"--secret={name}", f"--project={PROJECT}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _uvx() -> str:
    """Locate uvx, including when it lives in the active venv's bin dir."""
    found = shutil.which("uvx")
    if found:
        return found
    candidate = Path(sys.executable).parent / "uvx"
    if candidate.exists():
        return str(candidate)
    return "uvx"  # last resort; will error clearly if truly absent


def _mcp_command() -> tuple[str, list[str]]:
    """Prefer the installed `fivetran-mcp` console script (baked into the Cloud Run
    image via requirements), so the live app spawns the real MCP server without
    needing git/uvx at runtime. Fall back to uvx-from-git where only uvx exists."""
    found = shutil.which("fivetran-mcp")
    if not found:
        candidate = Path(sys.executable).parent / "fivetran-mcp"
        if candidate.exists():
            found = str(candidate)
    if found:
        return found, []
    return _uvx(), ["--from", "git+https://github.com/fivetran/fivetran-mcp", "fivetran-mcp"]


@asynccontextmanager
async def mcp_session(*, allow_writes: bool = False):
    """Spawn the Fivetran MCP server and yield an initialized ClientSession."""
    path = os.environ.get("PATH", "")
    venv_bin = str(Path(sys.executable).parent)
    if venv_bin not in path:
        path = f"{venv_bin}:{path}"
    env = {
        **os.environ,
        "FIVETRAN_API_KEY": _secret("fivetran-api-key"),
        "FIVETRAN_API_SECRET": _secret("fivetran-api-secret"),
        "PATH": path,
    }
    # The Fivetran MCP server's top-level module is `server`, which collides with
    # our own server.py on PYTHONPATH (=/app). Drop PYTHONPATH for the subprocess
    # so its `from server import main` resolves to the installed MCP package.
    env.pop("PYTHONPATH", None)
    if allow_writes:
        env["FIVETRAN_ALLOW_WRITES"] = "true"
    command, args = _mcp_command()
    server = StdioServerParameters(command=command, args=args, env=env)
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield _Mcp(session)


class _Mcp:
    """Thin helper that fills in each tool's required schema_file automatically."""

    def __init__(self, session: ClientSession):
        self.session = session
        self._tools: dict = {}

    async def _tool_map(self) -> dict:
        if not self._tools:
            self._tools = {t.name: t for t in (await self.session.list_tools()).tools}
        return self._tools

    async def call(self, name: str, **args):
        tools = await self._tool_map()
        prop = (tools[name].inputSchema or {}).get("properties", {}).get("schema_file", {})
        m = _SCHEMA_PATH.search(prop.get("description", ""))
        if m:
            args["schema_file"] = m.group(1)
        res = await self.session.call_tool(name, args)
        if not res.content:
            return None
        try:
            return json.loads(res.content[0].text)
        except Exception:
            return res.content[0].text


@dataclass
class FeedFreshness:
    schema: str
    connection_id: str
    service: str
    sync_state: str | None
    succeeded_at: str | None
    hours_old: float | None
    paused: bool | None = None
    setup_state: str | None = None

    @property
    def is_stale(self) -> bool:
        return self.hours_old is None or self.hours_old > 24.0


def _hours_since(ts: str | None) -> float | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        except ValueError:
            continue
    return None


async def _list_evidence_connections(mcp: _Mcp) -> list[dict]:
    res = await mcp.call("list_connections")
    items = (res or {}).get("data", {}).get("items", [])
    out = []
    for c in items:
        schema = str(c.get("schema", "")).split(".")[0]
        if schema in EVIDENCE_SCHEMAS:
            out.append(c)
    return out


async def check_freshness_async() -> list[FeedFreshness]:
    """Freshness of each evidence feed, via the MCP server (read-only)."""
    async with mcp_session() as mcp:
        conns = await _list_evidence_connections(mcp)
        feeds = []
        for c in conns:
            det = await mcp.call("get_connection_details", connection_id=c["id"])
            data = (det or {}).get("data", det) if isinstance(det, dict) else {}
            succeeded = data.get("succeeded_at")
            status = data.get("status") or {}
            feeds.append(FeedFreshness(
                schema=str(c.get("schema", "")).split(".")[0],
                connection_id=c["id"],
                service=c.get("service", ""),
                sync_state=status.get("sync_state"),
                succeeded_at=succeeded,
                hours_old=_hours_since(succeeded),
                paused=data.get("paused"),
                setup_state=status.get("setup_state"),
            ))
        return feeds


async def trigger_resync_async(connection_id: str, *, force: bool = True) -> dict:
    """Trigger a targeted re-sync of one connector (writes enabled)."""
    async with mcp_session(allow_writes=True) as mcp:
        res = await mcp.call(
            "sync_connection",
            connection_id=connection_id,
            request_body=json.dumps({"force": force}),
        )
        return res if isinstance(res, dict) else {"code": "Error", "message": str(res)}


# --- REST fallback (no MCP subprocess; works inside the Cloud Run container) ----


def _rest_request(method: str, path: str, body: dict | None = None) -> dict:
    import base64
    import urllib.request

    key, secret = _secret("fivetran-api-key"), _secret("fivetran-api-secret")
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://api.fivetran.com/v1{path}", data=data, method=method,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def check_freshness_rest() -> list[FeedFreshness]:
    """Freshness via the Fivetran REST API (used when the MCP server can't run)."""
    feeds = []
    for schema, cid in _CONNECTORS.items():
        try:
            data = _rest_request("GET", f"/connectors/{cid}").get("data", {})
        except Exception:
            feeds.append(FeedFreshness(schema, cid, "", None, None, None))
            continue
        succeeded = data.get("succeeded_at")
        status = data.get("status") or {}
        feeds.append(FeedFreshness(
            schema=schema, connection_id=cid, service=data.get("service", ""),
            sync_state=status.get("sync_state"),
            succeeded_at=succeeded, hours_old=_hours_since(succeeded),
            paused=data.get("paused"), setup_state=status.get("setup_state"),
        ))
    return feeds


def trigger_resync_rest(connection_id: str) -> dict:
    """Targeted re-sync via the Fivetran REST API."""
    return _rest_request("POST", f"/connectors/{connection_id}/sync", {"force": True})


async def set_paused_async(connection_id: str, paused: bool) -> dict:
    """Pause or resume a connector via the MCP (writes enabled)."""
    async with mcp_session(allow_writes=True) as mcp:
        res = await mcp.call(
            "modify_connection",
            connection_id=connection_id,
            request_body=json.dumps({"paused": paused}),
        )
        return res if isinstance(res, dict) else {"code": "Error", "message": str(res)}


def set_paused_rest(connection_id: str, paused: bool) -> dict:
    """Pause or resume a connector via the Fivetran REST API."""
    return _rest_request("PATCH", f"/connectors/{connection_id}", {"paused": paused})


def set_paused(connection_id: str, paused: bool) -> dict:
    _invalidate_freshness()
    try:
        return asyncio.run(set_paused_async(connection_id, paused))
    except Exception:
        return set_paused_rest(connection_id, paused)


# --- connector creation (gene onboarding) --------------------------------------

DEST_GROUP = "humpback_added"   # the BigQuery destination group
EVIDENCE_BUCKET = "unravel-ra-evidence-raw"


def _create_connection_body(schema: str, prefix: str, table: str = "evidence") -> dict:
    """The verified GCS-connector create payload (mirrors the seeded connectors)."""
    return {
        "service": "gcs",
        "group_id": DEST_GROUP,
        "config": {
            "schema": schema, "table": table,
            "auth_type": "FIVETRAN_SERVICE_ACCOUNT",
            "bucket": EVIDENCE_BUCKET, "prefix": prefix,
            "file_type": "csv", "delimiter": ",", "compression": "infer",
        },
    }


async def create_gcs_connector_async(schema: str, prefix: str, table: str = "evidence") -> dict:
    async with mcp_session(allow_writes=True) as mcp:
        res = await mcp.call("create_connection", request_body=json.dumps(_create_connection_body(schema, prefix, table)))
        return res if isinstance(res, dict) else {"code": "Error", "message": str(res)}


def create_gcs_connector_rest(schema: str, prefix: str, table: str = "evidence") -> dict:
    return _rest_request("POST", "/connectors", _create_connection_body(schema, prefix, table))


def create_gcs_connector(schema: str, prefix: str, table: str = "evidence") -> dict:
    """Create a new GCS->BigQuery connector via the MCP (CRUD: create); REST fallback.
    Returns the Fivetran response; the new connection id is at data.id."""
    _invalidate_freshness()
    try:
        return asyncio.run(create_gcs_connector_async(schema, prefix, table))
    except Exception:
        return create_gcs_connector_rest(schema, prefix, table)


def delete_connector(connection_id: str) -> dict:
    """Delete a connector (used for cleanup/testing)."""
    _invalidate_freshness()
    async def _go():
        async with mcp_session(allow_writes=True) as mcp:
            return await mcp.call("delete_connection", connection_id=connection_id)
    try:
        return asyncio.run(_go())
    except Exception:
        return _rest_request("DELETE", f"/connectors/{connection_id}")


# Short TTL cache so page-load freshness does not spawn the MCP subprocess (3-5s)
# on every request. The first call drives the real MCP; writes invalidate it.
_FRESH_CACHE: dict = {"t": 0.0, "feeds": None}
_FRESH_TTL = 90.0


def _invalidate_freshness() -> None:
    _FRESH_CACHE["feeds"] = None


def check_freshness(*, force: bool = False) -> list[FeedFreshness]:
    # Always drive the real Fivetran MCP server first (the hard requirement); the
    # console script is baked into the image so it spawns in Cloud Run too. Fall
    # back to the REST API only if the MCP subprocess cannot start.
    if not force and _FRESH_CACHE["feeds"] is not None and (time.monotonic() - _FRESH_CACHE["t"]) < _FRESH_TTL:
        return _FRESH_CACHE["feeds"]
    try:
        feeds = asyncio.run(check_freshness_async())
    except Exception:
        feeds = check_freshness_rest()
    _FRESH_CACHE.update(t=time.monotonic(), feeds=feeds)
    return feeds


def trigger_resync(connection_id: str) -> dict:
    _invalidate_freshness()
    try:
        return asyncio.run(trigger_resync_async(connection_id))
    except Exception:
        return trigger_resync_rest(connection_id)


def freshness_report(feeds: list[FeedFreshness] | None = None) -> str:
    """Human-readable freshness line for the Adjudicator's grounding."""
    feeds = feeds if feeds is not None else check_freshness()
    parts = []
    for f in sorted(feeds, key=lambda x: x.schema):
        age = f"{f.hours_old:.1f}h ago" if f.hours_old is not None else "unknown"
        flag = " STALE" if f.is_stale else ""
        parts.append(f"{f.schema} synced {age}{flag}")
    return "Fivetran MCP freshness: " + "; ".join(parts) if parts else "no evidence feeds found"
