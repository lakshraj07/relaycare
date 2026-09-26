"""Demand-driven gene onboarding into the Fivetran-synced warehouse.

When a gene is repeatedly resolved live (outside the onboarded commons), the
system recommends promoting it. Onboarding stages the gene's population evidence
to GCS and has the agent CREATE a new Fivetran GCS connector via the MCP
(create_connection), then sync it, so the gene's evidence lands in the
Fivetran-synced BigQuery warehouse. This is the agent orchestrating Fivetran end
to end: a real connector created on demand, a real sync, real data in BigQuery.

Lookup counts live in Firestore (collection `GeneLookups`); a gene crossing the
threshold surfaces an onboarding recommendation in the Data explorer.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request

PROJECT = "unravel-ra"
BUCKET = "unravel-ra-evidence-raw"
GNOMAD_API = "https://gnomad.broadinstitute.org/api"
ONBOARD_THRESHOLD = 3                              # live lookups before recommending
CORE_GENES = {"MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"}   # already in the warehouse
_COLL = "GeneLookups"
_VARIANT_CAP = 1200                                # keep the staged CSV demo-sized

_GNOMAD_GENE_Q = (
    "query G($s:String!){gene(gene_symbol:$s,reference_genome:GRCh38)"
    "{variants(dataset:gnomad_r4){variant_id exome{ac an} genome{ac an}}}}"
)


def _client(client=None):
    if client is not None:
        return client
    from google.cloud import firestore
    return firestore.Client(project=PROJECT)


def _safe(gene: str) -> str:
    return "".join(c for c in (gene or "").lower() if c.isalnum())


# --- lookup counting -----------------------------------------------------------


def record_lookup(gene: str | None, *, client=None) -> None:
    """Count one live lookup of `gene` (skip the core genes already onboarded)."""
    if not gene or gene.upper() in CORE_GENES:
        return
    try:
        from google.cloud import firestore
        c = _client(client)
        c.collection(_COLL).document(_safe(gene)).set({
            "gene": gene.upper(),
            "count": firestore.Increment(1),
            "last_seen": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception:
        pass  # counting is best-effort; never block a resolution on it


def onboard_status(*, client=None) -> dict:
    """Lookup counts + onboarding recommendations for every seen gene."""
    c = _client(client)
    genes = []
    for doc in c.collection(_COLL).stream():
        d = doc.to_dict()
        onboarded = bool(d.get("onboarded"))
        count = d.get("count", 0) or 0
        genes.append({
            "gene": d.get("gene"), "count": count, "onboarded": onboarded,
            "connection_id": d.get("connection_id"), "schema": d.get("schema"),
            "n_variants": d.get("n_variants"),
            "recommended": (not onboarded) and count >= ONBOARD_THRESHOLD,
        })
    genes.sort(key=lambda g: (g["onboarded"], -g["count"]))
    return {"genes": genes, "threshold": ONBOARD_THRESHOLD}


def onboarded_gene_set(*, client=None) -> set[str]:
    c = _client(client)
    return {d.to_dict().get("gene") for d in c.collection(_COLL).stream()
            if d.to_dict().get("onboarded")}


# --- the onboarding pipeline ---------------------------------------------------


def _gene_variants(gene: str, cap: int = _VARIANT_CAP) -> list[tuple]:
    """gnomAD v4 variants (with joint AF) for a gene, as warehouse-shaped rows."""
    body = json.dumps({"query": _GNOMAD_GENE_Q, "variables": {"s": gene}}).encode()
    req = urllib.request.Request(
        GNOMAD_API, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    variants = (((data.get("data") or {}).get("gene") or {}).get("variants")) or []
    rows = []
    for v in variants[:cap]:
        parts = (v.get("variant_id") or "").split("-")
        if len(parts) != 4:
            continue
        ac = an = 0
        for part in ("exome", "genome"):
            d = v.get(part)
            if d:
                ac += d.get("ac") or 0
                an += d.get("an") or 0
        af = (ac / an) if an else ""
        rows.append((parts[0], parts[1], parts[2], parts[3], gene.upper(), af))
    return rows


def _build_csv(rows: list[tuple]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["chromosome", "position", "reference_allele", "alternate_allele", "gene_symbol", "gnomad_af"])
    w.writerows(rows)
    return buf.getvalue()


def _stage_to_gcs(prefix: str, csv_text: str) -> str:
    from google.cloud import storage
    blob = storage.Client(project=PROJECT).bucket(BUCKET).blob(f"{prefix}/evidence.csv")
    blob.upload_from_string(csv_text, content_type="text/csv")
    return f"gs://{BUCKET}/{prefix}/evidence.csv"


def onboard_gene(gene: str, *, client=None) -> dict:
    """Stage `gene`'s evidence to GCS, have the agent create a Fivetran connector
    via the MCP, sync it, and mark the gene onboarded. Returns the new connection."""
    gene_u = (gene or "").upper()
    if not gene_u:
        raise ValueError("gene is required")
    safe = _safe(gene_u)
    schema = f"onboarded_{safe}"

    rows = _gene_variants(gene_u)
    if not rows:
        raise ValueError(f"no gnomAD variants found for {gene_u}")
    gcs_uri = _stage_to_gcs(schema, _build_csv(rows))

    from .fivetran_mcp import create_gcs_connector, trigger_resync
    res = create_gcs_connector(schema, schema)
    cid = (res or {}).get("data", {}).get("id")
    if not cid:
        raise RuntimeError(f"create_connection failed: {res}")
    sync = trigger_resync(cid)

    from google.cloud import firestore
    _client(client).collection(_COLL).document(safe).set({
        "gene": gene_u, "onboarded": True, "connection_id": cid,
        "schema": f"{schema}.evidence", "n_variants": len(rows), "gcs_uri": gcs_uri,
        "onboarded_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    return {"ok": True, "gene": gene_u, "connection_id": cid, "schema": f"{schema}.evidence",
            "n_variants": len(rows), "gcs_uri": gcs_uri, "sync": sync}
