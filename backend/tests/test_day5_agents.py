"""Unit tests for the deterministic tool-logic behind the agents.

The five agents themselves are real Gemini LlmAgents (unravel/agents.py), validated
live by scripts/run_adjudication.py and eval/adjudicator_eval.py. This file covers
the auditable deterministic logic they call as tools, the Resolution Planner's
information-value math (planner.plan_next_evidence) and the watch helpers, offline
via the pure demo registry (no BigQuery / Firestore / LLM).
"""

from __future__ import annotations

from unravel import registry, watch
from unravel.acmg import Ledger, Strength
from unravel.evidence import EvidenceContext
from unravel.planner import plan_next_evidence
from unravel.registry import HERO


def _trap_ctx() -> EvidenceContext:
    """The withheld trap's molecular ledger: PM2 + AlphaMissense-strong PP3 = 5 pts (0.81)."""
    led = Ledger(variant="MLH1 demo")
    led.add("PM2", source="gnomAD v4", detail="absent", strength=Strength.SUPPORTING)
    led.add("PP3", source="AlphaMissense", detail="am 0.99", strength=Strength.STRONG)
    return EvidenceContext(ledger=led, gene_symbol="MLH1", review_stars=1)


# --- Resolution Planner tool-logic (plan_next_evidence) ------------------------


def test_planner_recommends_a_crossing_experiment():
    plan = plan_next_evidence(_trap_ctx())
    assert plan.current_points == 5
    assert plan.gap_to_actionable == 1
    assert plan.steps, "should propose candidate experiments"
    assert any(s.crosses_actionable for s in plan.steps)
    assert "crossing the actionable line" in plan.recommendation


def test_planner_skips_criteria_already_in_the_ledger():
    plan = plan_next_evidence(_trap_ctx())
    assert all(not (s.code == "PP3") for s in plan.steps)


def test_planner_projected_posteriors_are_real_math():
    plan = plan_next_evidence(_trap_ctx())
    for s in plan.steps:
        assert 0.0 <= s.projected_posterior <= 1.0
        assert s.projected_posterior >= plan.current_posterior - 1e-9


def test_planner_when_nothing_crosses_says_so():
    plan = plan_next_evidence(EvidenceContext(ledger=Ledger(variant="far")))
    assert plan.gap_to_actionable == 6
    assert not any(s.crosses_actionable for s in plan.steps)
    assert "No single experiment crosses" in plan.recommendation


def test_planner_as_dict_shape():
    d = plan_next_evidence(_trap_ctx()).as_dict()
    assert {"variant", "current_points", "current_posterior", "gap_to_actionable",
            "recommendation", "steps"} <= set(d)


# --- family matching tool-logic (Cascade / Steward read this) ------------------


def test_match_affected_patients_finds_carriers_and_relatives():
    match = registry.match_affected_patients(HERO.key, data=registry.build_resources())
    # HERO carriers: Diane + Mei (the equity arm); their five at-risk relatives
    living = [c for c in match["carriers"] if not c.get("deceased")]
    assert len(living) == 2
    assert len(match["relatives"]) == 5


# --- watch helpers (no BigQuery) -----------------------------------------------


def test_watch_patient_name_helper():
    p = {"name": [{"given": ["Diane"], "family": "Marchetti"}], "id": "diane"}
    assert watch._patient_name(p) == "Diane Marchetti"


def test_watch_gid_helper_roundtrips_the_coordinate():
    assert watch._gid(HERO.key) == HERO.gid
