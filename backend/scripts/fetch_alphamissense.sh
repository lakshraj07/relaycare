#!/usr/bin/env bash
# Extract AlphaMissense (hg38) pathogenicity scores for the Lynch-syndrome genes.
#
# AlphaMissense is Unravel's PP3 / BP4 evidence stream (a ClinGen-calibrated
# in-silico missense predictor; supporting evidence, never the classifier). There
# is no public BigQuery copy, so we stream the bulk hg38 table from the public
# DeepMind bucket and filter to the five Lynch-gene GRCh38 coordinate windows on
# the fly, so the multi-GB file is never stored locally.
#
# Output CSV is keyed like the ClinVar / gnomAD slices
# (chromosome, position, reference_allele, alternate_allele) for the join, plus
# gene_symbol, am_pathogenicity (0..1), and am_class. The file is then staged in
# GCS and synced into BigQuery by a Fivetran GCS connector.
#
# Gene windows match backend/_staging/lynch_gene_ranges.json (from fetch_gnomad.py).
#
# Run:  cd backend && bash scripts/fetch_alphamissense.sh
set -euo pipefail

URL="https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg38.tsv.gz"
OUT="$(dirname "$0")/../_staging/alphamissense_lynch.csv"
mkdir -p "$(dirname "$OUT")"

echo "Streaming AlphaMissense hg38 and filtering to Lynch genes..." >&2

curl -sL "$URL" | gzip -dc | awk -F'\t' '
BEGIN {
  OFS = ","
  print "chromosome,position,reference_allele,alternate_allele,gene_symbol,am_pathogenicity,am_class"
}
/^#/ { next }
{
  c = $1; p = $2 + 0; g = ""
  if      (c == "chr3" && p >= 36993350 && p <= 37050846) g = "MLH1"
  else if (c == "chr2" && p >= 47345158 && p <= 47387601) g = "EPCAM"
  else if (c == "chr2" && p >= 47403067 && p <= 47663146) g = "MSH2"
  else if (c == "chr2" && p >= 47695530 && p <= 47810063) g = "MSH6"
  else if (c == "chr7" && p >=  5970925 && p <=  6009106) g = "PMS2"
  if (g != "") { sub("chr", "", c); print c, $2, $3, $4, g, $9, $10 }
}
' > "$OUT"

echo "Wrote $(($(wc -l < "$OUT") - 1)) rows -> $OUT" >&2
