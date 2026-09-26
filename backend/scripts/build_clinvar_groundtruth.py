"""Build a ClinVar reclassification ground-truth set for the backtest (task #1).

Reads the public ClinVar tab-delimited dumps (downloaded to
backend/_staging/clinvar_history/) and selects variants that genuinely crossed a
classification boundary over time, using the dated per-submission assertion
history as the trajectory signal.

A variant qualifies as a reclassification CASE when, for a hereditary-cancer
gene of interest, its dated submissions show:
  - UPGRADE:   an "Uncertain significance" assertion dated early (<= EARLY_YEAR)
               AND a Pathogenic / Likely pathogenic assertion dated later
               (>= LATE_YEAR), with the current aggregate on the pathogenic side.
  - DOWNGRADE: an "Uncertain significance" (or P/LP) assertion dated early
               AND a Benign / Likely benign assertion dated later, with the
               current aggregate on the benign side.

For each selected variant we record the pre-state, post-state, direction, the
decoded 0-4 star review status of the current aggregate, and the full dated
submission trajectory. This is the labelled spine the parametric backtest
(task #3) replays.

Inputs (download first, both public, no gate):
  https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
  https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/submission_summary.txt.gz

Run:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/build_clinvar_groundtruth.py

Output (committed, small):
  backend/eval/clinvar_reclassification_groundtruth.json
"""

from __future__ import annotations

import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

STAGING = Path(__file__).resolve().parent.parent / "_staging" / "clinvar_history"
VARIANT_SUMMARY = STAGING / "variant_summary.txt.gz"
SUBMISSION_SUMMARY = STAGING / "submission_summary.txt.gz"
OUT_DIR = Path(__file__).resolve().parent.parent / "eval"
OUT_FILE = OUT_DIR / "clinvar_reclassification_groundtruth.json"

# Hereditary-cancer genes: the 5 Lynch genes (our demo + warehouse) plus a
# curated spread of other syndromes for cohort breadth across disease domains.
GENES = {
    # Lynch / mismatch repair
    "MLH1", "MSH2", "MSH6", "PMS2", "EPCAM",
    # Hereditary breast / ovarian
    "BRCA1", "BRCA2", "PALB2", "CHEK2", "ATM",
    # Li-Fraumeni, polyposis, Cowden, Peutz-Jeghers, hereditary diffuse gastric
    "TP53", "APC", "MUTYH", "PTEN", "STK11", "CDH1",
}

EARLY_YEAR = 2021   # an "uncertain" assertion at or before this year = pre-state
LATE_YEAR = 2022    # a resolved assertion at or after this year = post-state
TARGET = 100        # cap on selected cases

VUS = "uncertain significance"
PATH = {"pathogenic", "likely pathogenic", "pathogenic/likely pathogenic"}
BENIGN = {"benign", "likely benign", "benign/likely benign"}


def stars(review_status: str) -> int:
    """Decode a ClinVar review-status string to its 0-4 gold-star rating."""
    r = (review_status or "").strip().lower()
    if "practice guideline" in r:
        return 4
    if "reviewed by expert panel" in r:
        return 3
    if "multiple submitters" in r and "no conflict" in r:
        return 2
    if "conflicting" in r:
        return 1
    if "single submitter" in r:
        return 1
    return 0


def norm_sig(sig: str) -> str:
    """Normalise a clinical-significance string to a comparison key."""
    s = (sig or "").strip().lower()
    s = re.sub(r"\(.*?\)", "", s).strip()      # drop trailing qualifiers
    s = s.split(";")[0].strip()                 # take the leading assertion
    return s


def year_of(date_str: str) -> int | None:
    """Pull a 4-digit year from a ClinVar date field (various formats)."""
    m = re.search(r"(19|20)\d{2}", date_str or "")
    return int(m.group(0)) if m else None


def header_index(line: str) -> dict[str, int]:
    cols = line.lstrip("#").rstrip("\n").split("\t")
    return {name: i for i, name in enumerate(cols)}


def load_variant_index() -> dict[str, dict]:
    """VariationID -> {gene, name, current_sig, review_status, stars} for GRCh38
    rows in our gene set."""
    if not VARIANT_SUMMARY.exists():
        raise SystemExit(f"missing {VARIANT_SUMMARY}; download it first")
    idx: dict[str, dict] = {}
    with gzip.open(VARIANT_SUMMARY, "rt", encoding="utf-8", errors="replace") as fh:
        cols = header_index(next(fh))
        ci = lambda n: cols[n]  # noqa: E731
        gi, asmi, vidi = ci("GeneSymbol"), ci("Assembly"), ci("VariationID")
        sigi, revi, namei = ci("ClinicalSignificance"), ci("ReviewStatus"), ci("Name")
        chri, posi = ci("Chromosome"), ci("PositionVCF")
        refi, alti = ci("ReferenceAlleleVCF"), ci("AlternateAlleleVCF")
        maxi = max(gi, asmi, vidi, sigi, revi, namei, chri, posi, refi, alti)
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) <= maxi:
                continue
            if f[asmi] != "GRCh38":
                continue
            genes = set(re.split(r"[;,|]", f[gi]))
            hit = genes & GENES
            if not hit:
                continue
            # GRCh38 VCF coordinate -> canonical gid (the warehouse join key).
            chrom, pos, ref, alt = f[chri], f[posi], f[refi], f[alti]
            gid = (f"{chrom}-{pos}-{ref}-{alt}"
                   if chrom and pos.isdigit() and ref not in ("", "na") and alt not in ("", "na")
                   else None)
            vid = f[vidi]
            idx[vid] = {
                "gene": sorted(hit)[0],
                "name": f[namei],
                "gid": gid,
                "current_sig": f[sigi],
                "review_status": f[revi],
                "stars": stars(f[revi]),
            }
    return idx


def load_submissions(varids: set[str]) -> dict[str, list[dict]]:
    """VariationID -> [ {sig, date, year, review_status, stars, submitter, scv} ]"""
    if not SUBMISSION_SUMMARY.exists():
        raise SystemExit(f"missing {SUBMISSION_SUMMARY}; download it first")
    subs: dict[str, list[dict]] = defaultdict(list)
    with gzip.open(SUBMISSION_SUMMARY, "rt", encoding="utf-8", errors="replace") as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                # The real header is the tab-delimited "#VariationID\t...ClinicalSignificance..."
                # line, distinct from the descriptive "#VariationID: ..." comment block.
                if line.lower().startswith("#variationid") and "ClinicalSignificance" in line:
                    header = header_index(line)
                continue
            if header is None:
                continue
            f = line.rstrip("\n").split("\t")
            vid = f[header["VariationID"]]
            if vid not in varids:
                continue
            date = f[header["DateLastEvaluated"]]
            subs[vid].append({
                "sig": f[header["ClinicalSignificance"]],
                "date": date,
                "year": year_of(date),
                "review_status": f[header["ReviewStatus"]],
                "stars": stars(f[header["ReviewStatus"]]),
                "submitter": f[header["Submitter"]],
                "scv": f[header["SCV"]],
            })
    return subs


def classify_trajectory(current_sig: str, submissions: list[dict]) -> dict | None:
    """Return a reclassification case dict if the dated submissions cross a
    boundary, else None."""
    cur = norm_sig(current_sig)
    cur_side = "path" if cur in PATH else "benign" if cur in BENIGN else None
    if cur_side is None:
        return None  # current aggregate must be resolved (not still VUS)

    early_vus = [s for s in submissions
                 if norm_sig(s["sig"]) == VUS and s["year"] and s["year"] <= EARLY_YEAR]
    if not early_vus:
        return None

    if cur_side == "path":
        late = [s for s in submissions
                if norm_sig(s["sig"]) in PATH and s["year"] and s["year"] >= LATE_YEAR]
        direction = "upgrade"
    else:
        late = [s for s in submissions
                if norm_sig(s["sig"]) in BENIGN and s["year"] and s["year"] >= LATE_YEAR]
        direction = "downgrade"
    if not late:
        return None

    pre = min(early_vus, key=lambda s: s["year"])
    post = max(late, key=lambda s: s["year"])
    return {
        "direction": direction,
        "pre_state": {"significance": "Uncertain significance",
                      "year": pre["year"], "stars": pre["stars"]},
        "post_state": {"significance": post["sig"], "year": post["year"],
                       "stars": post["stars"]},
    }


def main() -> None:
    print("indexing variant_summary (GRCh38, gene set)...")
    vindex = load_variant_index()
    print(f"  {len(vindex):,} candidate variants in {len(GENES)} genes")

    print("scanning submission_summary for dated trajectories...")
    subs = load_submissions(set(vindex))
    print(f"  {len(subs):,} variants have submission history")

    cases = []
    for vid, info in vindex.items():
        if info["gid"] is None:
            continue  # need a GRCh38 coordinate to drive the cohort + warehouse
        traj = classify_trajectory(info["current_sig"], subs.get(vid, []))
        if traj is None:
            continue
        history = sorted(subs[vid], key=lambda s: (s["year"] or 0))
        cases.append({
            "variation_id": vid,
            "gene": info["gene"],
            "name": info["name"],
            "gid": info["gid"],
            "current_significance": info["current_sig"],
            "current_review_status": info["review_status"],
            "current_stars": info["stars"],
            **traj,
            "n_submissions": len(history),
            "trajectory": [
                {"year": s["year"], "significance": s["sig"],
                 "stars": s["stars"], "submitter": s["submitter"]}
                for s in history
            ],
        })

    # Cache the full pool (gitignored) so the selection can be re-tuned without
    # re-streaming the ~780MB of source files.
    STAGING.mkdir(parents=True, exist_ok=True)
    (STAGING / "clinvar_groundtruth_full.json").write_text(json.dumps(cases, indent=2))

    def dist(rows):
        d, s, g = defaultdict(int), defaultdict(int), defaultdict(int)
        for c in rows:
            d[c["direction"]] += 1
            s[c["current_stars"]] += 1
            g[c["gene"]] += 1
        return dict(d), {str(k): v for k, v in sorted(s.items())}, dict(sorted(g.items()))

    full_dir, full_star, full_gene = dist(cases)
    print(f"  full pool: by_direction={full_dir} by_stars={full_star}")

    # Stratified selection for a usable backtest: balance the two directions
    # (both the escalation and the de-escalation arm must be well represented),
    # and within each direction round-robin across genes so Lynch and the other
    # syndromes all appear. Within a gene, prefer higher review confidence and
    # more submissions (cleaner labels).
    key = lambda c: (c["current_stars"], c["n_submissions"])  # noqa: E731

    def take(direction: str, n: int, used: set[str]) -> list[dict]:
        by_gene: dict[str, list] = defaultdict(list)
        for c in sorted([c for c in cases if c["direction"] == direction],
                        key=key, reverse=True):
            if c["variation_id"] not in used:
                by_gene[c["gene"]].append(c)
        out: list[dict] = []
        genes = sorted(by_gene)
        while len(out) < n and any(by_gene[g] for g in genes):
            for g in genes:
                if len(out) >= n:
                    break
                if by_gene[g]:
                    c = by_gene[g].pop(0)
                    out.append(c)
                    used.add(c["variation_id"])
        return out

    used: set[str] = set()
    half = TARGET // 2
    selected = take("upgrade", half, used)
    selected += take("downgrade", TARGET - len(selected), used)
    # Backfill from whichever arm still has supply if one ran short.
    if len(selected) < TARGET:
        selected += take("upgrade", TARGET - len(selected), used)
    if len(selected) < TARGET:
        selected += take("downgrade", TARGET - len(selected), used)

    by_dir, by_star, by_gene = dist(selected)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "ClinVar variants with genuine dated reclassification "
                       "history, ground truth for the Unravel backtest.",
        "built": "2026-06-06",
        "source": "ClinVar variant_summary + submission_summary (NCBI FTP)",
        "criteria": {"early_year": EARLY_YEAR, "late_year": LATE_YEAR,
                     "genes": sorted(GENES)},
        "counts": {"total_candidates_scanned": len(vindex),
                   "reclassification_cases_found": len(cases),
                   "full_pool_by_direction": full_dir,
                   "full_pool_by_stars": full_star,
                   "selected": len(selected),
                   "by_direction": by_dir,
                   "by_gene": by_gene,
                   "by_stars": by_star},
        "cases": selected,
    }
    OUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"\nfound {len(cases)} reclassification cases; selected {len(selected)}")
    print(f"  selected by direction: {by_dir}")
    print(f"  selected by gene: {by_gene}")
    print(f"  selected by stars: {by_star}")
    print(f"wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
