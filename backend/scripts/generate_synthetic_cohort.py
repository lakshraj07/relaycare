"""Generate a bulk synthetic FHIR cohort around real ClinVar variants (task #2).

Builds 500-1,000 synthetic patients carrying variants drawn from the real
reclassification ground-truth set (backend/eval/clinvar_reclassification_groundtruth.json).
Each patient is a real FHIR R4 Patient + variant Observation in exactly the shape
the demo registry uses (so match_affected_patients / pedigree / detect_reclassifications
consume it unchanged), and the whole cohort is a SELF-DESCRIBING BACKTEST FIXTURE:
it also emits the synthetic warehouse "current" state and the expected outcome per
patient, so the backtest (task #3) can call

    detect_reclassifications(data=resources, current=warehouse_current)

and check every prediction against `expectations`, with no live BigQuery/Firestore.

Scenario mix (the controlled cohort, per the evaluation strategy):
  upgrade (true reclassification -> actionable)   ~18%
  downgrade (VUS -> benign -> reassure)           ~12%
  1-star trap (tempting flip -> withhold)          ~5%
  unchanged (stable, true negative)               ~65%
Overlays applied on top:
  deceased proband (actionable -> Steward ethics)  ~6%
  multi-family cascade (carrier + at-risk kin)    ~30% of actionable carriers
Ancestry is assigned from a diverse set and flagged for AlphaMissense
under-representation, to support the ancestry-aware predictor down-weighting
(task #18) and the predictor-bias honesty story.

The hand-crafted Diane demo registry is left untouched: this cohort is a separate
fixture, and the optional Firestore loader writes to its own Cohort* collections.

Run:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/generate_synthetic_cohort.py
  cd backend && PYTHONPATH=. .venv/bin/python scripts/generate_synthetic_cohort.py --n 800

Output (committed):
  backend/eval/synthetic_cohort.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from unravel import registry
from unravel.registry import VariantSpec

GROUND_TRUTH = Path(__file__).resolve().parent.parent / "eval" / "clinvar_reclassification_groundtruth.json"
OUT_FILE = Path(__file__).resolve().parent.parent / "eval" / "synthetic_cohort.json"

SEED = 38  # deterministic cohorts (p.Asn38, a nod to the hero variant)

# Diverse name pools by ancestry. `under` flags ancestries under-represented in
# AlphaMissense's training data (predictor-bias story, task #18). Illustrative,
# not a claim about any individual.
ANCESTRIES = {
    "European":      {"under": False, "given_f": ["Emma", "Charlotte", "Sophie", "Hannah", "Clara", "Nora"],
                      "given_m": ["Liam", "Noah", "Lukas", "Erik", "Felix", "Anton"], "family": ["Schmidt", "Novak", "Andersson", "Kovac", "Bauer", "Romano"]},
    "African":       {"under": True,  "given_f": ["Amara", "Zola", "Ngozi", "Fatima", "Aisha", "Thandiwe"],
                      "given_m": ["Kwame", "Tunde", "Sipho", "Chike", "Kofi", "Jabari"], "family": ["Okafor", "Mensah", "Dlamini", "Adeyemi", "Banda", "Nkosi"]},
    "East Asian":    {"under": True,  "given_f": ["Mei", "Yuki", "Hana", "Jia", "Soo-jin", "Lin"],
                      "given_m": ["Wei", "Haruto", "Min-jun", "Chen", "Ren", "Tao"], "family": ["Tanaka", "Chen", "Kim", "Wang", "Nguyen", "Park"]},
    "South Asian":   {"under": True,  "given_f": ["Priya", "Ananya", "Meera", "Sana", "Divya", "Reshma"],
                      "given_m": ["Rajesh", "Arjun", "Vikram", "Imran", "Karthik", "Dev"], "family": ["Patel", "Sharma", "Khan", "Reddy", "Singh", "Iyer"]},
    "Hispanic":      {"under": True,  "given_f": ["Lucia", "Sofia", "Valeria", "Camila", "Elena", "Marisol"],
                      "given_m": ["Mateo", "Diego", "Santiago", "Marco", "Javier", "Tomas"], "family": ["Romero", "Garcia", "Morales", "Reyes", "Castillo", "Vega"]},
    "Middle Eastern": {"under": True, "given_f": ["Layla", "Yasmin", "Noor", "Rania", "Dalia", "Salma"],
                      "given_m": ["Omar", "Yusuf", "Karim", "Tariq", "Sami", "Hadi"], "family": ["Haddad", "Khalil", "Nasser", "Rahman", "Aziz", "Mansour"]},
}
RELATIONSHIPS = [("sister", "female"), ("brother", "male"), ("daughter", "female"),
                 ("son", "male"), ("mother", "female"), ("maternal aunt", "female")]
ANCESTRY_URL = "https://unravel.health/fhir/ancestry"


def parse_hgvs(name: str) -> tuple[str, str]:
    c = re.search(r":(c\.[^ ]+)", name)
    p = re.search(r"\((p\.[^)]+)\)", name)
    return (c.group(1) if c else ""), (p.group(1) if p else "")


def post_significance(case: dict) -> str:
    return case.get("current_significance") or case["post_state"]["significance"]


class Builder:
    def __init__(self, n: int):
        self.rng = random.Random(SEED)
        self.n = n
        self.patients: list[dict] = []
        self.observations: list[dict] = []
        self.histories: list[dict] = []
        self.warehouse: dict[str, dict] = {}
        self.expectations: list[dict] = []
        self._pid = 0

    # -- helpers ----------------------------------------------------------------
    def _name(self, ancestry: str, gender: str) -> tuple[str, str]:
        a = ANCESTRIES[ancestry]
        given = self.rng.choice(a["given_f"] if gender == "female" else a["given_m"])
        return given, self.rng.choice(a["family"])

    def _birth(self, *, min_y=1945, max_y=2004) -> str:
        return f"{self.rng.randint(min_y, max_y)}-{self.rng.randint(1, 12):02d}-{self.rng.randint(1, 28):02d}"

    def _rec_date(self) -> str:
        return f"{self.rng.randint(2008, 2019)}-{self.rng.randint(1, 12):02d}-{self.rng.randint(1, 28):02d}"

    def _spec(self, case: dict, current: str) -> VariantSpec:
        hc, hp = parse_hgvs(case["name"])
        return VariantSpec(case["gid"], case["gene"], hc, hp, current)

    def _add_warehouse(self, gid: str, sig: str, simple: int, stars: int, year: int | None):
        self.warehouse[gid] = {
            "clinical_significance": sig,
            "clin_sig_simple": simple,
            "review_stars": stars,
            "last_evaluated": f"{year or 2024}-01-01",
        }

    def _patient(self, ancestry: str, gender: str, *, deceased=False, role=None,
                 relative_of=None, relationship=None, conditions=None, contactable=True) -> dict:
        self._pid += 1
        given, family = self._name(ancestry, gender)
        pid = f"cohort-{self._pid:04d}-{given}-{family}".lower().replace(" ", "-")
        email = f"{given}.{family}@example.com".lower() if contactable else None
        phone = f"+1-415-555-{self.rng.randint(1000, 9999)}" if (contactable and self.rng.random() < 0.6) else None
        p = registry._patient(pid, family, given, gender, self._birth(),
                              deceased=deceased, role=role, relative_of=relative_of,
                              relationship=relationship, conditions=conditions,
                              email=email, phone=phone)
        p.setdefault("extension", []).append({"url": ANCESTRY_URL, "valueString": ancestry})
        self.patients.append(p)
        return p

    def _carrier(self, case: dict, recorded_class: str, current_sig: str, *,
                 deceased=False, conditions=None, contactable=True) -> str:
        ancestry = self.rng.choice(list(ANCESTRIES))
        gender = self.rng.choice(["female", "male"])
        p = self._patient(ancestry, gender, deceased=deceased, role="carrier",
                          conditions=conditions, contactable=contactable)
        spec = self._spec(case, current_sig)
        oid = f"obs-{p['id']}"
        self.observations.append(
            registry._observation(oid, p["id"], spec, recorded_class, self._rec_date()))
        return p["id"], oid, ancestry

    def _relatives(self, proband_id: str, ancestry: str, k: int) -> int:
        made = 0
        for _ in range(k):
            rel, gender = self.rng.choice(RELATIONSHIPS)
            self._patient(ancestry, gender, role=None, relative_of=proband_id,
                          relationship=rel, contactable=self.rng.random() < 0.7)
            made += 1
        return made

    # -- scenario emitters ------------------------------------------------------
    def emit_actionable(self, case: dict):
        sig = post_significance(case)
        self._add_warehouse(case["gid"], sig, 1, case.get("current_stars", 3),
                            case["post_state"].get("year"))
        deceased = self.rng.random() < 0.12
        pid, oid, anc = self._carrier(case, "Uncertain significance", sig,
                                      deceased=deceased,
                                      conditions=[f"{case['gene']}-related cancer"])
        n_rel = 0
        if not deceased and self.rng.random() < 0.35:
            n_rel = self._relatives(pid, anc, self.rng.randint(1, 3))
        self.expectations.append({
            "patient_id": pid, "observation_id": oid, "gid": case["gid"],
            "gene": case["gene"], "ancestry": anc,
            "ancestry_underrepresented": ANCESTRIES[anc]["under"],
            "scenario": "deceased_actionable" if deceased else "upgrade_actionable",
            "expected_detection": True, "expected_direction": "escalation",
            "expected_action": "ethics" if deceased else "actionable",
            "cascade_relatives": n_rel,
        })

    def emit_trap(self, case: dict):
        # A tempting upgrade variant whose current evidence is only a 1-star
        # conflicting submission: detection fires, the agent must WITHHOLD.
        self._add_warehouse(case["gid"], "Conflicting classifications of pathogenicity",
                            1, 1, case["post_state"].get("year"))
        pid, oid, anc = self._carrier(case, "Uncertain significance",
                                      "Conflicting classifications of pathogenicity",
                                      conditions=[f"{case['gene']}-related cancer"])
        self.expectations.append({
            "patient_id": pid, "observation_id": oid, "gid": case["gid"],
            "gene": case["gene"], "ancestry": anc,
            "ancestry_underrepresented": ANCESTRIES[anc]["under"],
            "scenario": "trap_1star", "expected_detection": True,
            "expected_direction": "escalation", "expected_action": "withhold",
            "cascade_relatives": 0,
        })

    def emit_downgrade(self, case: dict):
        sig = post_significance(case)
        self._add_warehouse(case["gid"], sig, 0, case.get("current_stars", 3),
                            case["post_state"].get("year"))
        pid, oid, anc = self._carrier(case, "Uncertain significance", sig)
        self.expectations.append({
            "patient_id": pid, "observation_id": oid, "gid": case["gid"],
            "gene": case["gene"], "ancestry": anc,
            "ancestry_underrepresented": ANCESTRIES[anc]["under"],
            "scenario": "downgrade", "expected_detection": True,
            "expected_direction": "downgrade", "expected_action": "reassure",
            "cascade_relatives": 0,
        })

    # Same-category text variants: real ClinVar wording that differs from the
    # recorded value but does NOT cross a category boundary. The system must not
    # raise a false reclassification on these. This is the non-tautological test
    # of the category-collapse logic (a clinically already-actionable LP->P is
    # not a new VUS-crossing event; cosmetic benign churn is not an alarm).
    SAME_CAT_PATH = ["Likely pathogenic", "Pathogenic/Likely pathogenic"]
    SAME_CAT_BENIGN = ["Likely benign", "Benign/Likely benign"]

    def emit_hard_negative(self, case: dict, side: str):
        sig = post_significance(case)  # the warehouse current (resolved P or B)
        simple = 1 if side == "path" else 0
        self._add_warehouse(case["gid"], sig, simple, case.get("current_stars", 3),
                            case["post_state"].get("year"))
        recorded = self.rng.choice(self.SAME_CAT_PATH if side == "path" else self.SAME_CAT_BENIGN)
        pid, oid, anc = self._carrier(case, recorded, sig)
        self.expectations.append({
            "patient_id": pid, "observation_id": oid, "gid": case["gid"],
            "gene": case["gene"], "ancestry": anc,
            "ancestry_underrepresented": ANCESTRIES[anc]["under"],
            "scenario": "stable_textvariant", "expected_detection": False,
            "expected_direction": None, "expected_action": "none",
            "recorded_class": recorded, "current_class": sig,
            "cascade_relatives": 0,
        })

    def emit_unchanged(self, case: dict):
        # Tested AFTER the variant resolved: recorded == current, so no diff.
        sig = post_significance(case)
        simple = 1 if case["direction"] == "upgrade" else 0
        self._add_warehouse(case["gid"], sig, simple, case.get("current_stars", 3),
                            case["post_state"].get("year"))
        pid, oid, anc = self._carrier(case, sig, sig)
        self.expectations.append({
            "patient_id": pid, "observation_id": oid, "gid": case["gid"],
            "gene": case["gene"], "ancestry": anc,
            "ancestry_underrepresented": ANCESTRIES[anc]["under"],
            "scenario": "unchanged_stable", "expected_detection": False,
            "expected_direction": None, "expected_action": "none",
            "cascade_relatives": 0,
        })

    # -- driver -----------------------------------------------------------------
    def build(self, cases: list[dict]) -> dict:
        ups = [c for c in cases if c["direction"] == "upgrade"]
        downs = [c for c in cases if c["direction"] == "downgrade"]
        self.rng.shuffle(ups)
        self.rng.shuffle(downs)
        # Reserve disjoint variant subsets so each gid has ONE warehouse state.
        # Traps are overridden to a 1-star conflicting state regardless of their
        # real review; actionable variants keep their REAL review and must be 2+
        # star, so the safety floor's "act on 2+ star escalation" boundary lines
        # up with the labels (a real upgrade that currently sits at 1-star is not
        # yet actionable, and is left out of the actionable pool by design).
        n_trap = max(2, len(ups) // 4)
        trap_vars = ups[:n_trap]
        action_vars = [u for u in ups[n_trap:] if u.get("current_stars", 3) >= 2] or ups[n_trap:]

        plan = {
            "upgrade_actionable": round(self.n * 0.18),
            "downgrade": round(self.n * 0.12),
            "trap_1star": round(self.n * 0.05),
            "stable_textvariant": round(self.n * 0.08),
        }
        plan["unchanged_stable"] = self.n - sum(plan.values())

        for i in range(plan["upgrade_actionable"]):
            self.emit_actionable(action_vars[i % len(action_vars)])
        for i in range(plan["trap_1star"]):
            self.emit_trap(trap_vars[i % len(trap_vars)])
        for i in range(plan["downgrade"]):
            self.emit_downgrade(downs[i % len(downs)])
        # Hard negatives: text changes that do NOT cross a category boundary,
        # split across the pathogenic and benign sides. The real specificity test.
        for i in range(plan["stable_textvariant"]):
            if i % 2 == 0:
                self.emit_hard_negative(action_vars[i % len(action_vars)], "path")
            else:
                self.emit_hard_negative(downs[i % len(downs)], "benign")
        # Unchanged: reuse action + downgrade variants (recorded == current).
        stable_pool = action_vars + downs
        for i in range(plan["unchanged_stable"]):
            self.emit_unchanged(stable_pool[i % len(stable_pool)])

        return self._payload(plan)

    def _payload(self, plan: dict) -> dict:
        from collections import Counter
        scen = Counter(e["scenario"] for e in self.expectations)
        return {
            "description": "Synthetic FHIR cohort carrying real ClinVar variants with "
                           "genuine reclassification history. Self-describing backtest fixture.",
            "built": "2026-06-06",
            "seed": SEED,
            "counts": {
                "index_patients": len(self.expectations),
                "relatives": len(self.patients) - len(self.expectations),
                "total_patients": len(self.patients),
                "observations": len(self.observations),
                "unique_variants": len(self.warehouse),
                "by_scenario": dict(scen),
                "underrepresented_ancestry": sum(
                    1 for e in self.expectations if e["ancestry_underrepresented"]),
                "cascade_relatives_total": sum(e["cascade_relatives"] for e in self.expectations),
                "planned": plan,
            },
            "resources": {"Patient": self.patients, "Observation": self.observations,
                          "FamilyMemberHistory": self.histories},
            "warehouse_current": self.warehouse,
            "expectations": self.expectations,
        }


def load_to_firestore(payload: dict, client=None) -> None:
    """Optional: write the cohort to its OWN Firestore collections (Cohort*),
    leaving the hand-crafted demo registry untouched."""
    client = client or registry.get_client()
    mapping = {"Patient": "CohortPatient", "Observation": "CohortObservation",
               "FamilyMemberHistory": "CohortFamilyMemberHistory"}
    for kind, coll_name in mapping.items():
        coll = client.collection(coll_name)
        for doc in coll.list_documents():
            doc.delete()
        for res in payload["resources"].get(kind, []):
            coll.document(res["id"]).set(res)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600, help="index patients (500-1000)")
    ap.add_argument("--firestore", action="store_true", help="also load into Cohort* collections")
    args = ap.parse_args()

    gt = json.loads(GROUND_TRUTH.read_text())
    cases = [c for c in gt["cases"] if c.get("gid")]
    builder = Builder(args.n)
    payload = builder.build(cases)

    OUT_FILE.write_text(json.dumps(payload, indent=2))
    c = payload["counts"]
    print(f"index patients:   {c['index_patients']}")
    print(f"relatives:        {c['relatives']}")
    print(f"total patients:   {c['total_patients']}")
    print(f"observations:     {c['observations']}")
    print(f"unique variants:  {c['unique_variants']}")
    print(f"by scenario:      {c['by_scenario']}")
    print(f"under-rep anc.:   {c['underrepresented_ancestry']}/{c['index_patients']}")
    print(f"cascade kin:      {c['cascade_relatives_total']}")
    print(f"wrote {OUT_FILE}")

    if args.firestore:
        load_to_firestore(payload)
        print("loaded into Cohort* Firestore collections")


if __name__ == "__main__":
    main()
