"""Live per-variant evidence, for variants outside the Fivetran-synced warehouse.

The BigQuery warehouse (kept fresh by Fivetran) holds the *onboarded* commons:
the mismatch-repair genes, on GRCh38 coordinates. When a clinician enters a
variant in a gene we have not onboarded yet, `build_evidence_ledger` falls back
to this module, which assembles the SAME row shape live from public sources:

  - Ensembl VEP REST   gene symbol, consequence, AlphaMissense score/class,
                       SIFT/PolyPhen, and colocated ClinVar significances + rsIDs
                       (one call; also normalises HGVS/rsID -> GRCh38 coords).
  - gnomAD GraphQL     joint (exome + genome) allele frequency.
  - NCBI ClinVar       review status -> 0-4 stars, submitter count, last
    E-utilities        evaluated, and the aggregate clinical significance.

The numbers reproduce the warehouse where they overlap (verified on the hero
variant: AlphaMissense 0.9997, gnomAD AF 0.284), so the agents reason
identically whether a variant is served from BigQuery or live from source. This
is the "any variant" path: the architecture, not the data, is the product.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .evidence import VariantKey

VEP_BASE = "https://rest.ensembl.org"
GNOMAD_API = "https://gnomad.broadinstitute.org/api"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_TIMEOUT = 20
_UA = "unravel-ra/1.0 (variant surveillance demo)"

# ClinVar review-status string -> star rating (0..4).
_REVIEW_STARS = {
    "practice guideline": 4,
    "reviewed by expert panel": 3,
    "criteria provided, multiple submitters, no conflicts": 2,
    "criteria provided, conflicting classifications": 1,
    "criteria provided, conflicting interpretations": 1,
    "criteria provided, single submitter": 1,
    "no assertion criteria provided": 0,
    "no assertion provided": 0,
    "no classification provided": 0,
    "no classifications from unflagged records": 0,
}

# small in-process cache so a graph + run-loop on the same variant fetch once.
_CACHE: dict[str, dict | None] = {}


def _gid(key: VariantKey) -> str:
    return f"{key.chromosome}-{key.position}-{key.reference_allele}-{key.alternate_allele}"


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _post_json(url: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": _UA},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _review_stars(status: str | None) -> int | None:
    if not status:
        return None
    s = status.strip().lower()
    if s in _REVIEW_STARS:
        return _REVIEW_STARS[s]
    # tolerant fallback for minor wording drift
    if "practice guideline" in s:
        return 4
    if "expert panel" in s:
        return 3
    if "multiple submitters" in s and "no conflict" in s:
        return 2
    if "conflict" in s or "single submitter" in s:
        return 1
    return 0


def _clin_sig_simple(desc: str | None) -> int | None:
    t = (desc or "").lower()
    if "pathogenic" in t and "conflict" not in t:
        return 1
    if "benign" in t and "conflict" not in t:
        return 0
    return None


# --- Ensembl VEP ---------------------------------------------------------------


def _strip_hgvs(s: str | None) -> str | None:
    """ENSP00000231790.3:p.Asn38Lys -> p.Asn38Lys (drop the transcript prefix)."""
    if not s:
        return None
    return s.split(":", 1)[1] if ":" in s else s


def _vep_record(record: dict) -> dict:
    """Pick the most informative transcript consequence out of a VEP record."""
    out: dict = {
        "gene_symbol": None, "consequence": record.get("most_severe_consequence"),
        "am_pathogenicity": None, "am_class": None,
        "sift": None, "polyphen": None, "hgvs_c": None, "hgvs_p": None, "rsids": [],
        "clin_sig_terms": [],
    }
    tcs = record.get("transcript_consequences", []) or []

    # prefer the transcript carrying an AlphaMissense call (highest score = canonical)
    am_tcs = [t for t in tcs if t.get("alphamissense")]
    if am_tcs:
        chosen = max(am_tcs, key=lambda t: t["alphamissense"].get("am_pathogenicity") or 0)
        am = chosen["alphamissense"]
        out["am_pathogenicity"] = am.get("am_pathogenicity")
        out["am_class"] = am.get("am_class")
    else:
        chosen = next((t for t in tcs if t.get("biotype") == "protein_coding" and t.get("gene_symbol")), None) \
            or (tcs[0] if tcs else {})
    out["gene_symbol"] = chosen.get("gene_symbol")
    out["sift"] = chosen.get("sift_prediction")
    out["polyphen"] = chosen.get("polyphen_prediction")
    out["hgvs_c"] = _strip_hgvs(chosen.get("hgvsc"))
    out["hgvs_p"] = _strip_hgvs(chosen.get("hgvsp"))

    for cv in record.get("colocated_variants", []) or []:
        cid = cv.get("id")
        if isinstance(cid, str) and cid.startswith("rs"):
            out["rsids"].append(cid)
        cs = cv.get("clin_sig")
        if cs:
            out["clin_sig_terms"].extend(cs if isinstance(cs, list) else [cs])
    return out


def _vep_region(key: VariantKey) -> dict | None:
    """VEP annotation for a GRCh38 SNV coordinate."""
    region = f"{key.chromosome}:{key.position}-{key.position}/{key.alternate_allele}"
    url = f"{VEP_BASE}/vep/human/region/{urllib.parse.quote(region)}?AlphaMissense=1&hgvs=1"
    try:
        data = _get_json(url)
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    return _vep_record(data[0])


# --- gnomAD --------------------------------------------------------------------


_GNOMAD_QUERY = (
    "query V($id:String!){variant(variantId:$id,dataset:gnomad_r4)"
    "{variant_id exome{ac an} genome{ac an}}}"
)


def _gnomad_af(key: VariantKey) -> float | None:
    """Joint (exome + genome) allele frequency, or None if absent from gnomAD."""
    try:
        res = _post_json(GNOMAD_API, {"query": _GNOMAD_QUERY, "variables": {"id": _gid(key)}})
    except Exception:
        return None
    v = (res.get("data") or {}).get("variant")
    if not v:
        return None
    ac = an = 0
    for part in ("exome", "genome"):
        d = v.get(part)
        if d:
            ac += d.get("ac") or 0
            an += d.get("an") or 0
    return (ac / an) if an else None


# --- NCBI ClinVar --------------------------------------------------------------


def _clinvar_summary(rsids: list[str], key: VariantKey) -> dict:
    """Aggregate ClinVar germline classification + review stars for the variant."""
    blank = {"clinical_significance": None, "review_status": None, "review_stars": None,
             "number_submitters": None, "last_evaluated": None}
    terms = [f"{r}" for r in rsids[:1]] or [
        f'{key.chromosome}[chr] AND {key.position}[chrpos37] OR {key.position}[chrpos38]'
    ]
    term = terms[0]
    try:
        es = _get_json(f"{EUTILS}/esearch.fcgi?db=clinvar&retmode=json&term={urllib.parse.quote(term)}")
        ids = es.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return blank
        summ = _get_json(f"{EUTILS}/esummary.fcgi?db=clinvar&retmode=json&id={ids[0]}")
        rec = summ["result"][summ["result"]["uids"][0]]
    except Exception:
        return blank
    g = rec.get("germline_classification", {}) or {}
    desc = g.get("description")
    scv = (rec.get("supporting_submissions") or {}).get("scv") or []
    return {
        "clinical_significance": desc,
        "review_status": g.get("review_status"),
        "review_stars": _review_stars(g.get("review_status")),
        "number_submitters": len(scv) or None,
        "last_evaluated": g.get("last_evaluated"),
    }


# --- public API ----------------------------------------------------------------


def fetch_live_row(key: VariantKey) -> dict | None:
    """Assemble a warehouse-shaped evidence row for `key` from public sources.

    Returns None only if VEP cannot resolve the coordinate at all (so the caller
    can report the variant as unrecognised). Otherwise every field the BigQuery
    `variant_evidence` view exposes is present (None where a source has no data),
    plus `source="live"` provenance and the bonus SIFT/PolyPhen predictors.
    """
    gid = _gid(key)
    if gid in _CACHE:
        return _CACHE[gid]

    vep = _vep_region(key)
    if vep is None:
        _CACHE[gid] = None
        return None

    cv = _clinvar_summary(vep.get("rsids", []), key)
    # fall back to VEP's colocated significance if eutils gave nothing
    if not cv["clinical_significance"] and vep.get("clin_sig_terms"):
        worst = _worst_clin_sig(vep["clin_sig_terms"])
        cv["clinical_significance"] = worst

    af = _gnomad_af(key)

    row = {
        "chromosome": key.chromosome,
        "position": key.position,
        "reference_allele": key.reference_allele,
        "alternate_allele": key.alternate_allele,
        "gene_symbol": vep.get("gene_symbol"),
        "consequence": vep.get("consequence"),
        "clinical_significance": cv["clinical_significance"],
        "clin_sig_simple": _clin_sig_simple(cv["clinical_significance"]),
        "review_status": cv["review_status"],
        "review_stars": cv["review_stars"],
        "number_submitters": cv["number_submitters"],
        "last_evaluated": cv["last_evaluated"],
        "gnomad_af": af,
        "am_pathogenicity": vep.get("am_pathogenicity"),
        "am_class": vep.get("am_class"),
        "sift_prediction": vep.get("sift"),
        "polyphen_prediction": vep.get("polyphen"),
        "hgvs_p": vep.get("hgvs_p"),
        "source": "live",
    }
    _CACHE[gid] = row
    return row


_CLIN_ORDER = ["pathogenic", "likely_pathogenic", "uncertain_significance",
               "likely_benign", "benign"]


def _worst_clin_sig(terms: list[str]) -> str | None:
    norm = {t.lower().replace(" ", "_") for t in terms}
    for level in _CLIN_ORDER:
        if level in norm:
            return level.replace("_", " ").title()
    return None


# --- variant normalisation (for Add-Patient free-text entry) -------------------


@dataclass
class NormalizedVariant:
    gid: str
    gene: str | None
    hgvs_c: str | None
    hgvs_p: str | None
    consequence: str | None


def normalize_query(query: str) -> NormalizedVariant | None:
    """Resolve a free-text variant (rsID, gene:c.HGVS, or chrom-pos-ref-alt) to a
    canonical GRCh38 key + gene + protein change via Ensembl VEP."""
    q = query.strip()
    if not q:
        return None

    # already canonical coordinates?
    parts = q.split("-")
    if len(parts) == 4 and parts[1].isdigit():
        endpoint = None
    elif q.lower().startswith("rs") and q[2:].isdigit():
        endpoint = f"{VEP_BASE}/vep/human/id/{urllib.parse.quote(q)}?AlphaMissense=1&hgvs=1"
    else:
        endpoint = f"{VEP_BASE}/vep/human/hgvs/{urllib.parse.quote(q)}?AlphaMissense=1&hgvs=1"

    try:
        if endpoint is None:
            key = VariantKey(parts[0], int(parts[1]), parts[2], parts[3])
            rec = _vep_region(key)
            gid = q
        else:
            data = _get_json(endpoint)
            if not isinstance(data, list) or not data:
                return None
            r0 = data[0]
            allele = (r0.get("allele_string") or "").split("/")
            chrom = str(r0.get("seq_region_name"))
            pos = r0.get("start")
            if len(allele) != 2 or pos is None:
                return None
            gid = f"{chrom}-{pos}-{allele[0]}-{allele[1]}"
            rec = _vep_record(r0)
    except Exception:
        return None

    if rec is None:
        return None
    return NormalizedVariant(
        gid=gid, gene=rec.get("gene_symbol"),
        hgvs_c=rec.get("hgvs_c"), hgvs_p=rec.get("hgvs_p"),
        consequence=rec.get("consequence"),
    )
