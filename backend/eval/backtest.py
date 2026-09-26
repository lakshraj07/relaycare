"""The backtest runner: drive the pipeline over the synthetic cohort and score it.

Loads the self-describing cohort fixture (synthetic patients carrying real ClinVar
variants, each with a hidden expected outcome), runs the real detection pipeline
plus the deterministic action safety-floor over every patient, and scores the
predictions against the ground-truth labels.

Two layers, both honest about what they measure:

  1. DETECTION (the Watcher).  Runs the real `detect_reclassifications` over the
     cohort's synthetic warehouse state. Non-circular: it exercises the actual
     diff logic. Yields precision / recall / F1 / specificity on "did we correctly
     flag a genuine reclassification, and in the right direction."

  2. ACTION (the safety-floor).  A deterministic policy that encodes the
     Adjudicator's documented decision boundary (3-4 star corroborated -> act;
     1-star / conflicting -> withhold; benign -> reassure; deceased actionable ->
     ethics). This is the auditable safety floor the LLM Adjudicator must agree
     with; the live LLM is validated separately on the demo cases by
     scripts/run_adjudication.py. Here we score the floor at scale, focusing on
     the safety-critical metrics: did it withhold on every 1-star trap, and did it
     never wrongly escalate a downgrade or a trap to family recontact.

Pure and fast (no BigQuery / Firestore / LLM): the metrics module (task #4) and
the calibration analysis (task #5) import `evaluate()` and build on this report.
"""

from __future__ import annotations

import json
from pathlib import Path

from unravel.detection import detect_reclassifications

COHORT = Path(__file__).resolve().parent / "synthetic_cohort.json"


def load_cohort(path: Path = COHORT) -> dict:
    return json.loads(path.read_text())


# --- the deterministic action safety-floor (mirrors the Adjudicator boundary) ---


def reference_action(direction: str, review_stars: int | None) -> str:
    """Map a detected reclassification to the safety-floor action.

    Encodes the Adjudicator's instruction: a benign move is reassurance; an
    escalation backed by a 2+ star (multiple-submitter / expert-panel) review is
    actionable; an escalation resting only on a 1-star or conflicting assertion is
    withheld pending higher-yield evidence; anything else is held conservatively.
    """
    if direction == "downgrade":
        return "reassure"
    if direction == "escalation":
        return "actionable" if (review_stars or 0) >= 2 else "withhold"
    return "withhold"


def final_action(action: str, *, deceased: bool) -> str:
    """A deceased proband never receives a direct recontact: route to ethics."""
    if action == "actionable" and deceased:
        return "ethics"
    return action


# --- metrics helpers -----------------------------------------------------------


def _binary_metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "specificity": round(spec, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
    }


# --- the backtest --------------------------------------------------------------


def evaluate(cohort: dict | None = None) -> dict:
    """Run detection + the action floor over the cohort and return a full report."""
    cohort = cohort or load_cohort()
    data = cohort["resources"]
    current = cohort["warehouse_current"]
    expectations = cohort["expectations"]

    deceased = {p["id"]: bool(p.get("deceasedBoolean"))
                for p in data["Patient"]}

    # Layer 1: real detection over the synthetic warehouse.
    detections = detect_reclassifications(data=data, current=current)
    by_pid = {r.patient_id: r for r in detections}

    # --- detection scoring ---
    tp = fp = fn = tn = 0
    dir_ok = dir_bad = 0
    for e in expectations:
        pid = e["patient_id"]
        got = pid in by_pid
        want = e["expected_detection"]
        if want and got:
            tp += 1
            if by_pid[pid].direction == e["expected_direction"]:
                dir_ok += 1
            else:
                dir_bad += 1
        elif want and not got:
            fn += 1
        elif not want and got:
            fp += 1
        else:
            tn += 1
    detection = _binary_metrics(tp, fp, fn, tn)
    detection["direction_accuracy"] = round(dir_ok / (dir_ok + dir_bad), 4) if (dir_ok + dir_bad) else 0.0

    # The positive detections cross a category boundary by construction, so flagging
    # them is a deterministic regression check, not skill. The non-tautological test
    # is SPECIFICITY on hard negatives: cases where the ClinVar text changes but the
    # category does not (e.g. "Likely pathogenic" -> "Pathogenic"), which must not be
    # flagged. This actually exercises the category-collapse logic.
    hard = [e for e in expectations if e["scenario"] == "stable_textvariant"]
    hard_fp = sum(1 for e in hard if e["patient_id"] in by_pid)
    detection["hard_negatives"] = {
        "n": len(hard),
        "false_positives": hard_fp,
        "specificity": round((len(hard) - hard_fp) / len(hard), 4) if hard else None,
        "note": "text changes that do not cross a category boundary; the real specificity test",
    }
    detection["positives_note"] = ("Reclassification positives cross a category boundary by "
                                   "construction; P/R/F1 here is a deterministic regression check, "
                                   "not an accuracy measurement.")

    # --- action scoring (over the cases that were correctly detected) ---
    actions = [a for a in ("actionable", "withhold", "reassure", "ethics")]
    confusion = {a: {b: 0 for b in actions} for a in actions}
    per_case = []
    for e in expectations:
        if not e["expected_detection"]:
            continue
        pid = e["patient_id"]
        r = by_pid.get(pid)
        if r is None:
            continue  # missed detection already counted as FN
        pred = final_action(reference_action(r.direction, r.review_stars),
                            deceased=deceased.get(pid, False))
        exp = e["expected_action"]
        if exp in confusion and pred in confusion[exp]:
            confusion[exp][pred] += 1
        per_case.append({"patient_id": pid, "scenario": e["scenario"],
                         "expected": exp, "predicted": pred,
                         "stars": r.review_stars, "direction": r.direction,
                         "ancestry_underrepresented": e["ancestry_underrepresented"]})

    correct = sum(confusion[a][a] for a in actions)
    total = sum(confusion[a][b] for a in actions for b in actions)

    # safety-critical: withhold behaviour and wrong escalations
    n_should_withhold = sum(confusion["withhold"].values())
    withhold_correct = confusion["withhold"]["withhold"]
    # a "dangerous escalation" = something that should be withheld or reassured but
    # was marked actionable / ethics (i.e. pushed toward family recontact)
    dangerous = (confusion["withhold"]["actionable"] + confusion["withhold"]["ethics"]
                 + confusion["reassure"]["actionable"] + confusion["reassure"]["ethics"])

    action = {
        "confusion": confusion,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "n_scored": total,
        "withhold_recall": round(withhold_correct / n_should_withhold, 4) if n_should_withhold else 0.0,
        "withhold_n": n_should_withhold,
        "dangerous_escalations": dangerous,
    }

    return {
        "cohort_counts": cohort["counts"],
        "detection": detection,
        "action": action,
        "per_case": per_case,
    }


def main() -> None:
    rep = evaluate()
    d, a = rep["detection"], rep["action"]
    print("=== DETECTION (real detect_reclassifications over the cohort) ===")
    print(f"  TP={d['tp']} FP={d['fp']} FN={d['fn']} TN={d['tn']}")
    print(f"  precision={d['precision']}  recall={d['recall']}  f1={d['f1']}")
    print(f"  specificity={d['specificity']}  FPR={d['false_positive_rate']}")
    print(f"  direction accuracy={d['direction_accuracy']}")
    print("\n=== ACTION (deterministic safety-floor) ===")
    print(f"  accuracy={a['accuracy']} over {a['n_scored']} detected cases")
    print(f"  withhold recall={a['withhold_recall']} on {a['withhold_n']} trap cases")
    print(f"  dangerous escalations (should-withhold/reassure -> recontact): {a['dangerous_escalations']}")
    print("  confusion (rows=expected, cols=predicted):")
    cols = ["actionable", "withhold", "reassure", "ethics"]
    print("    " + " ".join(f"{c[:6]:>8}" for c in cols))
    for exp in cols:
        print(f"  {exp[:8]:>8} " + " ".join(f"{a['confusion'][exp][c]:>8}" for c in cols))


if __name__ == "__main__":
    main()
