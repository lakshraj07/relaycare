"""Custom Fivetran connector (Connector SDK): gnomAD allele frequencies.

This is the "host Python on Fivetran" path. Instead of staging CSVs to GCS and
syncing the files, this connector pulls gnomAD v4 joint (exome + genome) allele
frequencies for the hereditary-cancer genes directly from the gnomAD GraphQL API
and upserts them into the destination. Fivetran runs, schedules and incrementally
syncs it, so the same evidence lands in BigQuery with no intermediate file.

It mirrors the schema of our GCS-based `gnomad.allele_frequency` table, so the
curated `evidence.variant_evidence` view joins it identically.

Local test:  cd backend/connectors/gnomad && fivetran debug
Deploy:      fivetran deploy --api-key <key> --destination <dest> --connection gnomad_sdk
"""

import json
import urllib.request

from fivetran_connector_sdk import Connector, Logging as log, Operations as op

DEFAULT_GENES = ["MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"]
GNOMAD_API = "https://gnomad.broadinstitute.org/api"
_QUERY = (
    "query G($s:String!){gene(gene_symbol:$s,reference_genome:GRCh38)"
    "{variants(dataset:gnomad_r4){variant_id exome{ac an} genome{ac an}}}}"
)


def schema(configuration: dict):
    return [{
        "table": "allele_frequency",
        "primary_key": ["chromosome", "position", "reference_allele", "alternate_allele"],
        "columns": {
            "chromosome": "STRING", "position": "INT",
            "reference_allele": "STRING", "alternate_allele": "STRING",
            "gene_symbol": "STRING", "allele_count": "INT",
            "allele_number": "INT", "allele_frequency": "DOUBLE",
        },
    }]


def _variants(gene: str):
    body = json.dumps({"query": _QUERY, "variables": {"s": gene}}).encode()
    req = urllib.request.Request(
        GNOMAD_API, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "unravel-fivetran-connector/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return (((data.get("data") or {}).get("gene") or {}).get("variants")) or []


def update(configuration: dict, state: dict):
    genes = [g.strip() for g in (configuration.get("genes", "") or "").split(",") if g.strip()] or DEFAULT_GENES
    for gene in genes:
        log.info(f"gnomAD connector: syncing {gene}")
        n = 0
        for v in _variants(gene):
            parts = (v.get("variant_id") or "").split("-")
            if len(parts) != 4:
                continue
            ac = an = 0
            for part in ("exome", "genome"):
                d = v.get(part)
                if d:
                    ac += d.get("ac") or 0
                    an += d.get("an") or 0
            yield op.upsert("allele_frequency", {
                "chromosome": parts[0], "position": int(parts[1]),
                "reference_allele": parts[2], "alternate_allele": parts[3],
                "gene_symbol": gene, "allele_count": ac, "allele_number": an,
                "allele_frequency": (ac / an) if an else None,
            })
            n += 1
        log.info(f"gnomAD connector: {gene} -> {n} variants")
        yield op.checkpoint({"last_gene": gene})


connector = Connector(update=update, schema=schema)

if __name__ == "__main__":
    connector.debug()
