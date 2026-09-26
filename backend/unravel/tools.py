"""FunctionTools for the five Unravel agents (the "hands").

The deterministic work, detecting the change, assembling the cited ACMG ledger and
calibrated posterior, ranking candidate experiments, matching the family, checking
Fivetran freshness, is exposed here as tools the LLM agents call. The agents (the
"brains", in agents.py) reason over what these tools return: they decide whether a
change matters, weigh review quality and withhold, choose the highest-yield next
experiment, and draft the recontact. This is the brain/hands split the agent
whitepapers prescribe: tools are deterministic and auditable; judgement is the LLM.

Every tool takes a patient_id and returns a JSON-serialisable dict.
"""

from __future__ import annotations

from . import registry
from .acmg import posterior_breakdown, score_posterior
from .detection import _category, _direction, _gid
from .evidence import build_evidence_ledger
from .planner import plan_next_evidence


def _client():
    from google.cloud import bigquery
    return bigquery.Client(project=registry.PROJECT)


def _resolve(patient_id: str):
    """Shared per-patient context: variant, ancestry-aware ledger, posterior."""
    data = registry.fetch_all()
    obs = next((o for o in data["Observation"]
                if o["subject"]["reference"].endswith(patient_id)), None)
    if obs is None:
        return None
    key = registry.observation_variant(obs)
    patient = next((p for p in data["Patient"] if p["id"] == patient_id), {})
    ur = registry.ancestry_underrepresented(patient)
    ctx = build_evidence_ledger(key, client=_client(), ancestry_underrepresented=ur)
    return {"data": data, "obs": obs, "key": key, "patient": patient,
            "ancestry_underrepresented": ur, "ctx": ctx,
            "gene": registry.observation_field(obs, "48018-6"),
            "hgvs_c": registry.observation_field(obs, "48004-6"),
            "hgvs_p": registry.observation_field(obs, "48005-3")}


# --- Watcher's tools -----------------------------------------------------------


def lookup_reclassification(patient_id: str) -> dict:
    """Look up how a patient's variant has moved: the classification the clinic
    recorded versus the current ClinVar classification, the review-star quality,
    and the direction of change. Use this to judge whether a change is worth
    escalating."""
    r = _resolve(patient_id)
    if r is None:
        return {"found": False}
    ctx, obs = r["ctx"], r["obs"]
    recorded = registry.recorded_classification(obs)
    current = ctx.clinical_significance
    direction = _direction(_category(recorded), _category(current, None))
    return {
        "found": True, "patient_id": patient_id,
        "gene": r["gene"], "variant": f"{r['gene']} {r['hgvs_c']}",
        "recorded_classification": recorded,
        "current_classification": current,
        "review_stars": ctx.review_stars,
        "direction": direction or "unchanged",
        "ancestry_underrepresented": r["ancestry_underrepresented"],
    }


def check_feed_freshness() -> dict:
    """Check how fresh each evidence feed (ClinVar, gnomAD, AlphaMissense) is via
    the live Fivetran MCP server, so a verdict accounts for stale data."""
    try:
        from .fivetran_mcp import freshness_report
        return {"freshness": freshness_report()}
    except Exception as e:
        return {"freshness": f"unavailable ({type(e).__name__})"}


# --- Adjudicator's tool --------------------------------------------------------


def assemble_evidence(patient_id: str) -> dict:
    """Assemble the cited ACMG/AMP evidence ledger and the calibrated Bayesian
    posterior for a patient's variant (points, probability, band, how far from the
    actionable line, and every cited criterion with its source). The posterior is
    computed deterministically; treat it as fact."""
    r = _resolve(patient_id)
    if r is None:
        return {"found": False}
    ctx = r["ctx"]
    post = score_posterior(ctx.ledger)
    return {
        "found": True, "variant": f"{r['gene']} {r['hgvs_c']}",
        "current_classification": ctx.clinical_significance,
        "review_stars": ctx.review_stars,
        "posterior": round(post.posterior, 3), "points": post.points,
        "band": post.band.value, "points_to_actionable": post.points_to_actionable,
        "ancestry_underrepresented": r["ancestry_underrepresented"],
        "cited_evidence": post.cited_lines(),
        "breakdown": posterior_breakdown(ctx.ledger),
    }


# --- Resolution Planner's tool -------------------------------------------------


def rank_next_experiments(patient_id: str) -> dict:
    """Return the candidate next experiments for a variant short of actionable
    (segregation, tumour MMR/IHC, MSI, functional, splicing) and the calibrated
    posterior each would reach. Use this to recommend the single highest-yield
    move; the projected posteriors are real Bayesian math."""
    r = _resolve(patient_id)
    if r is None:
        return {"found": False}
    plan = plan_next_evidence(r["ctx"])
    return {
        "found": True, "current_posterior": round(plan.current_posterior, 3),
        "current_band": plan.current_band, "gap_to_actionable": plan.gap_to_actionable,
        "candidates": [
            {"experiment": s.label, "acmg": f"{s.code} {s.strength}",
             "projected_posterior": s.projected_posterior,
             "crosses_actionable": s.crosses_actionable, "feasibility": s.feasibility}
            for s in plan.steps
        ],
    }


# --- Cascade Coordinator's tool ------------------------------------------------


def find_family(patient_id: str) -> dict:
    """Find THIS patient's family for recontact: the proband (the carrier) and
    their untested at-risk relatives, with contact details. Scoped to one
    pedigree, so a carrier in another family who happens to share the variant
    (their own separate case) is not pulled in here."""
    r = _resolve(patient_id)
    if r is None:
        return {"found": False}
    ped = registry.pedigree(patient_id, data=r["data"])
    members = ped["members"]
    carriers = [{"name": m["name"], "deceased": m["deceased"]}
                for m in members if m["carrier"]]
    relatives = [{"id": m["id"], "name": m["name"], "relationship": m["relationship"],
                  "email": m.get("email"),
                  "contactable": m.get("email") is not None}
                 for m in members if not m["carrier"] and m["relationship"] != "proband"]
    return {"found": True, "variant": f"{r['gene']} {r['hgvs_c']}",
            "carriers": carriers, "relatives": relatives,
            "living_carriers": [c for c in carriers if not c["deceased"]]}


# --- Steward's tool ------------------------------------------------------------


def steward_assessment(patient_id: str) -> dict:
    """Return the governance facts for a variant: any deceased carriers (who must
    be routed to ethics, never a direct letter) with their living relatives, and
    the cited evidence available for a draft ClinVar give-back submission."""
    r = _resolve(patient_id)
    if r is None:
        return {"found": False}
    match = registry.match_affected_patients(r["key"], data=r["data"])
    post = score_posterior(r["ctx"].ledger)
    deceased = []
    for c in match["carriers"]:
        if c.get("deceased"):
            p = c["patient"]
            living = [registry._person(rel["patient"], relationship=rel["relationship"],
                                       carrier=False)["name"]
                      for rel in match["relatives"] if rel.get("carrier_id") == p["id"]]
            deceased.append({"name": registry._person(p, relationship="carrier",
                                                      carrier=True)["name"],
                             "living_relatives": living})
    return {"found": True, "variant": f"{r['gene']} {r['hgvs_c']}",
            "current_classification": r["ctx"].clinical_significance,
            "deceased_carriers": deceased,
            "cited_evidence": post.cited_lines()}
