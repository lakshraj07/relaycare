"""Ancestry-aware predictor down-weighting (Council Q1 / task #18).

For a carrier of an ancestry under-represented in AlphaMissense's training data,
the PP3 strength is trusted one tier less, so a possibly biased predictor cannot
drive the verdict on its own. These tests pin the behaviour and the clean
side-by-side: Mei Tanaka carries the SAME variant as Diane, yet her molecular
posterior is lower because AlphaMissense is down-weighted for her ancestry.
"""

from __future__ import annotations

from unravel import registry
from unravel.acmg import Strength, score_posterior
from unravel.evidence import acmg_items_from_row, build_evidence_ledger
from unravel.registry import HERO

# A warehouse row for an AlphaMissense-strong, gnomAD-absent variant (Diane's HERO).
ROW = {"gene_symbol": "MLH1", "gnomad_af": None,
       "am_pathogenicity": 0.9997, "am_class": "likely_pathogenic"}


def _pp3(items):
    return next(i for i in items if i.code == "PP3")


def test_pp3_strength_is_lowered_one_tier():
    base = _pp3(acmg_items_from_row(ROW))
    down = _pp3(acmg_items_from_row(ROW, ancestry_underrepresented=True))
    assert base.effective_strength == Strength.STRONG      # am >= 0.99 -> Strong
    assert down.effective_strength == Strength.MODERATE    # down-weighted one tier
    assert "down-weighted" in down.detail


def test_benign_side_is_not_down_weighted():
    benign_row = {"gene_symbol": "MLH1", "gnomad_af": None,
                  "am_pathogenicity": 0.10, "am_class": "likely_benign"}
    base = acmg_items_from_row(benign_row)
    down = acmg_items_from_row(benign_row, ancestry_underrepresented=True)
    assert [i.code for i in base] == [i.code for i in down]  # BP4 unchanged


def test_posterior_is_lower_for_underrepresented_ancestry():
    euro = score_posterior(build_evidence_ledger(HERO.key, row=ROW).ledger)
    under = score_posterior(
        build_evidence_ledger(HERO.key, row=ROW, ancestry_underrepresented=True).ledger)
    assert euro.points == 5 and under.points == 3          # PP3 4->2
    assert under.posterior < euro.posterior
    assert build_evidence_ledger(HERO.key, row=ROW,
                                 ancestry_underrepresented=True).ancestry_underrepresented


def test_registry_classifies_ancestry():
    data = registry.build_resources()
    patients = {p["id"]: p for p in data["Patient"]}
    assert registry.patient_ancestry(patients["diane-marchetti"]) == "European"
    assert registry.patient_ancestry(patients["mei-tanaka"]) == "East Asian"
    assert registry.ancestry_underrepresented(patients["diane-marchetti"]) is False
    assert registry.ancestry_underrepresented(patients["mei-tanaka"]) is True


def test_diane_vs_mei_same_variant_different_posterior():
    # Mei is a "silent Diane": same HERO variant, but East Asian -> down-weighted.
    data = registry.build_resources()
    patients = {p["id"]: p for p in data["Patient"]}
    diane_ur = registry.ancestry_underrepresented(patients["diane-marchetti"])
    mei_ur = registry.ancestry_underrepresented(patients["mei-tanaka"])
    diane = score_posterior(build_evidence_ledger(HERO.key, row=ROW,
                                                  ancestry_underrepresented=diane_ur).ledger)
    mei = score_posterior(build_evidence_ledger(HERO.key, row=ROW,
                                                ancestry_underrepresented=mei_ur).ledger)
    assert mei.posterior < diane.posterior
