"""Build the small public watchlist fixture used by the RelayCare demo."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "eval" / "synthetic_cohort.json"
METRICS = ROOT / "backend" / "eval" / "metrics.json"
OUTPUT = ROOT / "frontend" / "public" / "demo-cohort.json"


def component(observation: dict, code: str) -> str | None:
    for item in observation.get("component", []):
        coding = item.get("code", {}).get("coding", [{}])[0]
        if coding.get("code") == code:
            return item.get("valueString")
    return None


def name(patient: dict) -> str:
    item = (patient.get("name") or [{}])[0]
    return f"{' '.join(item.get('given', []))} {item.get('family', '')}".strip()


def main() -> None:
    fixture = json.loads(SOURCE.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    patients = {p["id"]: p for p in fixture["resources"]["Patient"]}
    outcomes = {x["patient_id"]: x for x in metrics["per_case"]}
    current = fixture["warehouse_current"]
    rows: list[dict] = []

    # The public site needs a fast, representative watchlist, not the private
    # warehouse dump. Keep enough varied cases for the dashboard views and tour.
    for observation in fixture["resources"]["Observation"][:36]:
        pid = observation["subject"]["reference"].split("/")[-1]
        patient = patients[pid]
        gid = component(observation, "81252-9")
        warehouse = current.get(gid, {})
        outcome = outcomes.get(pid, {})
        recorded = component(observation, "53037-8") or "Uncertain significance"
        current_class = warehouse.get("clinical_significance") or recorded
        direction = outcome.get("direction", "unchanged")
        pathogenic = "pathogenic" in current_class.lower()
        benign = "benign" in current_class.lower()
        points = 8 if pathogenic else (0 if benign else 2)
        posterior = 0.94 if pathogenic else (0.03 if benign else 0.52)
        band = "pathogenic" if pathogenic else ("benign" if benign else "uncertain")
        rows.append({
            "patient_id": pid,
            "patient_name": name(patient),
            "deceased": bool(patient.get("deceasedBoolean", False)),
            "gene": component(observation, "48018-6") or "GENE",
            "hgvs_c": component(observation, "48004-6") or "unknown",
            "hgvs_p": component(observation, "48005-3"),
            "variant": f"{component(observation, '48018-6') or 'GENE'} {component(observation, '48004-6') or 'unknown'}",
            "recorded_class": recorded,
            "recorded_date": observation.get("effectiveDateTime"),
            "current_class": current_class,
            "review_stars": warehouse.get("review_stars") or outcome.get("stars") or 0,
            "direction": direction,
            "reclassified": direction != "unchanged",
            "points": points,
            "posterior": posterior,
            "band": band,
            "points_to_actionable": max(0, 6 - points),
            "gnomad_af": None,
            "am_pathogenicity": None,
            "am_class": None,
            "ancestry": "synthetic",
            "ancestry_downweighted": bool(outcome.get("ancestry_underrepresented", False)),
            "source": "demo fixture",
            "warehouse_sql": None,
            "cited": ["Public RelayCare demo fixture; synthetic patient record."],
            "breakdown": {
                "variant": f"{component(observation, '48018-6') or 'GENE'} {component(observation, '48004-6') or 'unknown'}",
                "prior": 0.1,
                "prior_posterior": 0.1,
                "steps": [],
                "total_points": points,
                "odds_path": 1.0,
                "posterior": posterior,
                "band": band,
                "points_to_actionable": max(0, 6 - points),
                "is_actionable": pathogenic,
                "actionable_line": {"points": 6, "posterior": 0.9},
            },
        })

    OUTPUT.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
