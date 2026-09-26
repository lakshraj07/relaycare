#!/usr/bin/env bash
# Per-residue AlphaMissense pathogenicity for the Lynch genes (for the 3D story).
#
# The unified evidence slice keeps AlphaMissense at the variant level; the
# structural viewer needs it at the *residue* level (mean pathogenicity over all
# substitutions at each amino-acid position) to draw the heatmap and find
# pathogenic 3D neighbours. We stream the bulk hg38 table once more and aggregate
# to per-residue means in a single awk pass, so only the small result is kept.
#
# Output columns: gene, uniprot, residue, mean_am, n_subs.
#
# Run:  cd backend && bash scripts/fetch_alphamissense_residue.sh
set -euo pipefail

URL="https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg38.tsv.gz"
OUT="$(dirname "$0")/../_staging/alphamissense_residue.csv"
mkdir -p "$(dirname "$OUT")"

echo "Streaming AlphaMissense and aggregating per residue..." >&2

{
  echo "gene,uniprot,residue,mean_am,n_subs"
  curl -sL "$URL" | gzip -dc | awk -F'\t' '
  /^#/ { next }
  {
    c = $1; p = $2 + 0; g = ""
    if      (c == "chr3" && p >= 36993350 && p <= 37050846) g = "MLH1"
    else if (c == "chr2" && p >= 47345158 && p <= 47387601) g = "EPCAM"
    else if (c == "chr2" && p >= 47403067 && p <= 47663146) g = "MSH2"
    else if (c == "chr2" && p >= 47695530 && p <= 47810063) g = "MSH6"
    else if (c == "chr7" && p >=  5970925 && p <=  6009106) g = "PMS2"
    if (g == "") next
    uni = $6; pv = $8
    res = pv; gsub(/[^0-9]/, "", res); res = res + 0
    if (res == 0) next
    key = g "|" uni "|" res
    sum[key] += $9; cnt[key] += 1
  }
  END {
    for (k in sum) {
      n = split(k, a, "|")
      printf "%s,%s,%d,%.4f,%d\n", a[1], a[2], a[3], sum[k] / cnt[k], cnt[k]
    }
  }' | sort -t, -k1,1 -k3,3n
} > "$OUT"

echo "Wrote $(($(wc -l < "$OUT") - 1)) residues -> $OUT" >&2
