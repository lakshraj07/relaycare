"""Smoke-test the Fivetran MCP server against the live unravel account.

This proves the "deep MCP" gate: the agent layer can drive Fivetran through the
official MCP server (github.com/fivetran/fivetran-mcp), not just the raw REST
API. It spawns the server over stdio, lists the tools it exposes, then calls the
read-only ones (list connections, connection details, schema config) for the
ClinVar GCS connector.

The Fivetran MCP server uses a deliberate guardrail: every tool requires a
`schema_file` argument naming the bundled OpenAPI definition for that call, which
the caller is meant to read first and then echo back to confirm intent. We honour
that pattern by parsing each tool's required schema path from its own description
and passing it. This is good context engineering on Fivetran's part and is
exactly how the ADK agent will call these tools on Day 4.

Writes (sync_connection / resync_connection) are intentionally left disabled
(FIVETRAN_ALLOW_WRITES unset) so the smoke test never triggers a real sync; we
only confirm those write tools are registered. Mid-loop targeted re-sync wiring
lands Day 4, inside the Adjudicator.

Credentials are read at runtime from Secret Manager (fivetran-api-key /
fivetran-api-secret in project unravel-ra); nothing secret is stored in the repo.

Run:  cd backend && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/fivetran_mcp_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT = "unravel-ra"
SYNC_TOOLS = {"sync_connection", "resync_connection"}
READ_TOOLS = ("list_connections", "get_connection_details", "get_connection_schema_config")
_SCHEMA_PATH = re.compile(r"(open-api-definitions/[^'\"]+\.json)")


def _secret(name: str) -> str:
    out = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         f"--secret={name}", f"--project={PROJECT}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _schema_file(tool) -> str | None:
    """Pull the required schema_file path out of a tool's own description."""
    prop = (tool.inputSchema or {}).get("properties", {}).get("schema_file", {})
    m = _SCHEMA_PATH.search(prop.get("description", ""))
    return m.group(1) if m else None


def _json(result):
    if not result.content:
        return None
    try:
        return json.loads(result.content[0].text)
    except Exception:
        return result.content[0].text


async def main() -> None:
    server = StdioServerParameters(
        command="uvx",
        args=["--from", "git+https://github.com/fivetran/fivetran-mcp", "fivetran-mcp"],
        env={
            "FIVETRAN_API_KEY": _secret("fivetran-api-key"),
            "FIVETRAN_API_SECRET": _secret("fivetran-api-secret"),
            # FIVETRAN_ALLOW_WRITES omitted -> read-only.
            "PATH": os.environ.get("PATH", ""),
        },
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = {t.name: t for t in (await session.list_tools()).tools}
            print(f"MCP server up. {len(tools)} tools exposed.")
            print("  sync/control registered:",
                  ", ".join(sorted(SYNC_TOOLS & tools.keys())) or "NONE")
            print("  read tools registered:  ",
                  ", ".join(t for t in READ_TOOLS if t in tools))
            print()

            def call(name, **args):
                sf = _schema_file(tools[name])
                if sf:
                    args["schema_file"] = sf  # confirm intent, per the guardrail
                return session.call_tool(name, args)

            # 1) list_connections
            conns = _json(await call("list_connections")) or {}
            items = conns.get("data", {}).get("items", [])
            print(f"list_connections -> {len(items)} connection(s):")
            target = None
            for c in items:
                print(f"  - {c.get('id')} | {c.get('schema')} | {c.get('service')} "
                      f"| sync={c.get('status', {}).get('sync_state')}")
                if c.get("service") == "gcs" or "clinvar" in str(c.get("schema")):
                    target = c.get("id")
            print()
            if not target:
                print("No ClinVar/GCS connector found; stopping.")
                return

            # 2) get_connection_details (freshness, the input to mid-loop re-sync)
            det = _json(await call("get_connection_details", connection_id=target))
            data = det.get("data", det) if isinstance(det, dict) else {}
            status = data.get("status", {})
            print(f"get_connection_details({target}):")
            print(f"  service={data.get('service')} setup={status.get('setup_state')} "
                  f"sync={status.get('sync_state')} succeeded_at={data.get('succeeded_at')}")
            print()

            # 3) get_connection_schema_config (the schema-management path)
            sch = _json(await call("get_connection_schema_config", connection_id=target))
            sdata = sch.get("data", sch) if isinstance(sch, dict) else {}
            schemas = sdata.get("schemas", {})
            tables = sorted(
                t for sc in schemas.values() for t in sc.get("tables", {})
            )
            print(f"get_connection_schema_config({target}): "
                  f"{len(schemas)} schema(s), tables={tables[:8]}")

    print("\nSmoke test OK: Fivetran MCP drives listing, details, and schema live.")


if __name__ == "__main__":
    asyncio.run(main())
