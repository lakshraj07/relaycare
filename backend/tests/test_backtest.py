"""Parametric backtest over the synthetic cohort (task #3).

Each synthetic patient becomes a test case: the real detection pipeline must flag
(or correctly not flag) the reclassification, in the right direction, and the
deterministic action safety-floor must produce the expected clinical action. This
turns the 600-patient cohort into 600+ assertions, and pins the safety-critical
properties (every 1-star trap is withheld; nothing that should be withheld or
reassured is ever escalated to family recontact).

The live Gemini Adjudicator is validated separately on the demo cases by
scripts/run_adjudication.py; here we score the auditable floor at scale, with no
BigQuery / Firestore / LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from unravel.detection import detect_reclassifications

# Import the backtest module from backend/eval without shadowing the `eval` builtin.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import backtest  # noqa: E402

COHORT_PATH = backtest.COHORT
pytestmark = pytest.mark.skipif(
    not COHORT_PATH.exists(),
    reason="synthetic cohort not generated (run scripts/generate_synthetic_cohort.py)",
)

if COHORT_PATH.exists():
    COHORT = backtest.load_cohort()
    DETECTIONS = detect_reclassifications(
        data=COHORT["resources"], current=COHORT["warehouse_current"])
    BY_PID = {r.patient_id: r for r in DETECTIONS}
    DECEASED = {p["id"]: bool(p.get("deceasedBoolean")) for p in COHORT["resources"]["Patient"]}
    REPORT = backtest.evaluate(COHORT)
    EXPECTATIONS = COHORT["expectations"]
    DETECTED_EXP = [e for e in EXPECTATIONS if e["expected_detection"]]
else:  # keep collection working even if the fixture is absent
    COHORT = {}; DETECTIONS = []; BY_PID = {}; DECEASED = {}
    REPORT = {}; EXPECTATIONS = []; DETECTED_EXP = []


# --- per-patient parametric cases ----------------------------------------------


@pytest.mark.parametrize("exp", EXPECTATIONS, ids=[e["patient_id"] for e in EXPECTATIONS])
def test_detection_per_patient(exp):
    """The Watcher flags exactly the patients whose evidence actually moved."""
    detected = exp["patient_id"] in BY_PID
    assert detected == exp["expected_detection"], (
        f"{exp['scenario']}: expected_detection={exp['expected_detection']}, got {detected}")
    if exp["expected_detection"]:
        assert BY_PID[exp["patient_id"]].direction == exp["expected_direction"]


@pytest.mark.parametrize("exp", DETECTED_EXP, ids=[e["patient_id"] for e in DETECTED_EXP])
def test_action_per_patient(exp):
    """The safety-floor produces the expected clinical action for each case."""
    r = BY_PID[exp["patient_id"]]
    pred = backtest.final_action(
        backtest.reference_action(r.direction, r.review_stars),
        deceased=DECEASED.get(exp["patient_id"], False))
    assert pred == exp["expected_action"], (
        f"{exp['scenario']} (stars={r.review_stars}, dir={r.direction}): "
        f"expected {exp['expected_action']}, got {pred}")


# --- aggregate metric / safety gates -------------------------------------------


def test_detection_metrics_perfect():
    d = REPORT["detection"]
    assert d["precision"] == 1.0 and d["recall"] == 1.0 and d["f1"] == 1.0
    assert d["false_positive_rate"] == 0.0
    assert d["direction_accuracy"] == 1.0


def test_every_trap_is_withheld():
    a = REPORT["action"]
    assert a["withhold_n"] >= 20, "cohort should contain a meaningful set of traps"
    assert a["withhold_recall"] == 1.0


def test_no_dangerous_escalations():
    # nothing that should be withheld or reassured may be pushed to recontact
    assert REPORT["action"]["dangerous_escalations"] == 0


def test_hard_negative_specificity():
    # the non-tautological detection test: text changes that don't cross a
    # category boundary (e.g. "Likely pathogenic" -> "Pathogenic") must not flag
    hn = REPORT["detection"]["hard_negatives"]
    assert hn["n"] >= 20, "need a meaningful set of hard negatives"
    assert hn["false_positives"] == 0
    assert hn["specificity"] == 1.0


def test_action_accuracy_on_cohort():
    assert REPORT["action"]["accuracy"] == 1.0


def test_cohort_is_large_and_diverse():
    c = REPORT["cohort_counts"]
    assert c["total_patients"] >= 500
    assert c["underrepresented_ancestry"] > 0
    # both arms present
    assert c["by_scenario"].get("upgrade_actionable", 0) > 0
    assert c["by_scenario"].get("downgrade", 0) > 0
    assert c["by_scenario"].get("trap_1star", 0) > 0
