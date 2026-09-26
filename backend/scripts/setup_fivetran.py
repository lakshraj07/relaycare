"""Reproduce Unravel's Fivetran pipeline: the BigQuery destination + the three
evidence connectors, created through the Fivetran MCP server.

Unravel's evidence commons is three Fivetran GCS->BigQuery connectors landing
ClinVar, gnomAD and AlphaMissense into BigQuery, which a curated view
(`evidence.variant_evidence`, see backend/sql/variant_evidence.sql) models into
the AI data plane the five ADK agents query.

This script is idempotent: it lists the existing connectors via the MCP and only
creates the ones that are missing, then triggers their initial sync. It assumes
the evidence CSVs are already staged in gs://unravel-ra-evidence-raw/<prefix>/
(see scripts/fetch_gnomad.py, fetch_alphamissense.sh, build_clinvar_groundtruth.py)
and that a BigQuery destination already exists in the Fivetran group.

Run:  cd backend && PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=. \
        .venv/bin/python scripts/setup_fivetran.py
"""

from __future__ import annotations

import asyncio

from unravel.fivetran_mcp import (
    DEST_GROUP, EVIDENCE_BUCKET, create_gcs_connector, mcp_session, trigger_resync,
)

# schema (BigQuery dataset) -> (GCS prefix, destination table)
CONNECTORS = {
    "clinvar": ("clinvar", "variant_summary"),
    "gnomad": ("gnomad", "allele_frequency"),
    "alphamissense": ("alphamissense", "scores"),
}


async def _existing_schemas() -> set[str]:
    async with mcp_session() as mcp:
        res = await mcp.call("list_connections")
        items = (res or {}).get("data", {}).get("items", [])
        return {str(c.get("schema", "")).split(".")[0] for c in items}


def main() -> None:
    print(f"Destination group: {DEST_GROUP}  ·  bucket: gs://{EVIDENCE_BUCKET}")
    existing = asyncio.run(_existing_schemas())
    print(f"Existing connector schemas: {sorted(existing) or 'none'}\n")

    for schema, (prefix, table) in CONNECTORS.items():
        if schema in existing:
            print(f"  [skip]   {schema}: already connected")
            continue
        print(f"  [create] {schema}: GCS gs://{EVIDENCE_BUCKET}/{prefix}/ -> {schema}.{table} via MCP create_connection")
        res = create_gcs_connector(schema, prefix, table)
        cid = (res or {}).get("data", {}).get("id")
        if not cid:
            print(f"           FAILED: {res}")
            continue
        sync = trigger_resync(cid)
        code = sync.get("code") if isinstance(sync, dict) else sync
        print(f"           created {cid}, initial sync: {code}")

    print("\nDone. The curated view recreates with: backend/sql/variant_evidence.sql")


if __name__ == "__main__":
    main()
