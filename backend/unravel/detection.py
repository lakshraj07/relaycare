"""detect_reclassifications: the Watcher's deterministic diff vs the registry.

This is plumbing, not the moat: it compares the classification each carrier's
variant was recorded with (the registry's memory) against the current ClinVar
classification in the evidence warehouse, and surfaces the ones that moved. The
Adjudicator decides whether a surfaced change is real and actionable; this step
only finds the candidates, deterministically.

A reclassification is an "escalation" when a variant the clinic recorded as
benign or uncertain now reads pathogenic (the Diane case), a "downgrade" when it
now reads benign (reassurance, not an alarm), or "lateral" otherwise.

`since` is an optional fail-open filter: when given, a detection is kept only if
the registry's record predates it (the clinic's knowledge is stale relative to
that date). With `since=None` every current-vs-recorded difference is reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from . import registry
from .evidence import EVIDENCE_VIEW, VariantKey


@dataclass(frozen=True)
class Reclassification:
    patient_id: str
    gene: str
    hgvs_c: str
    variant: VariantKey
    recorded_class: str
    recorded_date: str | None
    current_class: str
    review_stars: int | None
    last_evaluated: str | None
    direction: str  # 'escalation' | 'downgrade' | 'lateral'

    @property
    def is_escalation(self) -> bool:
        return self.direction == "escalation"


def _category(text: str | None, simple: int | None = None) -> str:
    """Collapse a classification to P / B / VUS."""
    if simple is not None:
        return {1: "P", 0: "B"}.get(simple, "VUS")
    t = (text or "").lower()
    if "pathogenic" in t and "conflict" not in t:
        return "P"
    if "benign" in t:
        return "B"
    return "VUS"


def _direction(recorded_cat: str, current_cat: str) -> str | None:
    if recorded_cat == current_cat:
        return None
    if current_cat == "P":
        return "escalation"
    if current_cat == "B":
        return "downgrade"
    return "lateral"


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def fetch_current(keys, client=None) -> dict[str, dict]:
    """Current warehouse classification for a set of VariantKeys, by gid."""
    keys = list({k for k in keys})
    if not keys:
        return {}
    from google.cloud import bigquery

    client = client or bigquery.Client(project=registry.PROJECT)
    gids = [k.gid if hasattr(k, "gid") else
            f"{k.chromosome}-{k.position}-{k.reference_allele}-{k.alternate_allele}"
            for k in keys]
    sql = f"""
      SELECT
        CONCAT(CAST(chromosome AS STRING), '-', CAST(position AS STRING), '-',
               reference_allele, '-', alternate_allele) AS gid,
        clinical_significance, clin_sig_simple, review_stars, last_evaluated
      FROM `{EVIDENCE_VIEW}`
      WHERE CONCAT(CAST(chromosome AS STRING), '-', CAST(position AS STRING), '-',
                   reference_allele, '-', alternate_allele) IN UNNEST(@gids)
    """
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("gids", "STRING", gids),
    ]))
    out: dict[str, dict] = {}
    for row in job.result():
        # keep the best-reviewed record per variant
        prev = out.get(row["gid"])
        if prev is None or (row["review_stars"] or 0) > (prev["review_stars"] or 0):
            out[row["gid"]] = dict(row)
    return out


def _gid(k: VariantKey) -> str:
    return f"{k.chromosome}-{k.position}-{k.reference_allele}-{k.alternate_allele}"


def detect_reclassifications(
    since: str | None = None,
    *,
    data=None,
    client=None,
    current=None,
) -> list[Reclassification]:
    """Diff the registry's recorded classifications against current ClinVar."""
    data = data or registry.fetch_all(client)
    observations = data["Observation"]

    keys = [registry.observation_variant(o) for o in observations]
    keys = [k for k in keys if k is not None]
    if current is None:
        current = fetch_current(keys, client)

    since_date = _parse_date(since)
    results: list[Reclassification] = []
    for obs in observations:
        key = registry.observation_variant(obs)
        if key is None:
            continue
        cur = current.get(_gid(key))
        if cur is None:
            continue  # variant not in warehouse; nothing to compare

        recorded = registry.recorded_classification(obs)
        recorded_cat = _category(recorded)
        current_cat = _category(cur.get("clinical_significance"), cur.get("clin_sig_simple"))
        direction = _direction(recorded_cat, current_cat)
        if direction is None:
            continue  # no change

        recorded_date = obs.get("effectiveDateTime")
        if since_date is not None:
            rec_d = _parse_date(recorded_date)
            if rec_d is not None and rec_d >= since_date:
                continue  # record is newer than the watch floor; not stale

        results.append(Reclassification(
            patient_id=obs["subject"]["reference"].split("/")[-1],
            gene=registry.observation_field(obs, "48018-6") or "",
            hgvs_c=registry.observation_field(obs, "48004-6") or "",
            variant=key,
            recorded_class=recorded or "",
            recorded_date=recorded_date,
            current_class=cur.get("clinical_significance") or "",
            review_stars=cur.get("review_stars"),
            last_evaluated=cur.get("last_evaluated"),
            direction=direction,
        ))
    return results
