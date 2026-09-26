"""Fetch gnomAD v4 (GRCh38) allele frequencies for the Lynch-syndrome genes.

gnomAD population frequency is Unravel's PM2 / BS1 / BA1 evidence stream (rare or
absent supports pathogenic; common refutes it). The public BigQuery copy of
gnomAD is only v2.1.1 on GRCh37, which would force a liftover against the GRCh38
ClinVar slice. To stay GRCh38-native we pull v4 directly from the gnomAD GraphQL
API, one gene at a time, and compute the joint (exomes + genomes) allele
frequency per variant.

Output is a CSV keyed exactly like the ClinVar slice
(chromosome, position, reference_allele, alternate_allele) so the unified
evidence view can join on the GRCh38 VCF coordinate. The file is then staged in
GCS and synced into BigQuery by a Fivetran GCS connector, mirroring ClinVar.

A companion gene-ranges JSON (GRCh38 chrom/start/stop per gene) is written next to
the CSV; the AlphaMissense extractor reads it to slice the bulk hg38 table.

Run:  cd backend && .venv/bin/python scripts/fetch_gnomad.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import requests

GENES = ["MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"]
API = "https://gnomad.broadinstitute.org/api"
OUT_DIR = Path(__file__).resolve().parent.parent / "_staging"

_QUERY = """
query LynchGene($symbol: String!) {
  gene(gene_symbol: $symbol, reference_genome: GRCh38) {
    gene_id
    chrom
    start
    stop
    variants(dataset: gnomad_r4) {
      variant_id
      pos
      ref
      alt
      exome { ac an }
      genome { ac an }
    }
  }
}
"""


def _fetch_gene(symbol: str) -> dict:
    """One gene's variants, retrying transient API hiccups."""
    for attempt in range(4):
        resp = requests.post(
            API, json={"query": _QUERY, "variables": {"symbol": symbol}}, timeout=180
        )
        if resp.status_code == 200 and "errors" not in resp.json():
            return resp.json()["data"]["gene"]
        wait = 3 * (attempt + 1)
        print(f"  {symbol}: retry in {wait}s (status {resp.status_code})", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"gnomAD API failed for {symbol}: {resp.text[:200]}")


def _joint_af(v: dict) -> tuple[int, int, float]:
    """Joint allele count / number / frequency across exomes and genomes."""
    ac = an = 0
    for src in ("exome", "genome"):
        s = v.get(src)
        if s:
            ac += s.get("ac") or 0
            an += s.get("an") or 0
    af = ac / an if an else 0.0
    return ac, an, af


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    csv_path = OUT_DIR / "gnomad_lynch.csv"
    ranges_path = OUT_DIR / "lynch_gene_ranges.json"

    ranges: dict[str, dict] = {}
    rows = 0
    with csv_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "chromosome", "position", "reference_allele", "alternate_allele",
            "gene_symbol", "allele_count", "allele_number", "allele_frequency",
        ])
        for symbol in GENES:
            gene = _fetch_gene(symbol)
            chrom = str(gene["chrom"])
            ranges[symbol] = {
                "gene_id": gene["gene_id"],
                "chrom": chrom,
                "start": gene["start"],
                "stop": gene["stop"],
            }
            variants = gene["variants"]
            for v in variants:
                ac, an, af = _joint_af(v)
                writer.writerow([
                    chrom, v["pos"], v["ref"], v["alt"],
                    symbol, ac, an, f"{af:.3e}",
                ])
            rows += len(variants)
            print(f"  {symbol}: {len(variants):>6} variants "
                  f"(chr{chrom}:{gene['start']}-{gene['stop']})")

    ranges_path.write_text(json.dumps(ranges, indent=2))
    print(f"\nWrote {rows} rows -> {csv_path}")
    print(f"Wrote gene ranges -> {ranges_path}")


if __name__ == "__main__":
    main()
