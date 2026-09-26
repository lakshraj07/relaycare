"""Tests for build_evidence_ledger, the warehouse-to-engine bridge.

These exercise the pure mapping from a warehouse row to ACMG criteria (no
BigQuery needed) and confirm the demo variant's real numbers behave: the 1-star
trap (absent from gnomAD, AlphaMissense-pathogenic) scores as Uncertain and is
withheld until family segregation tips it over.
"""

import pytest

from unravel.acmg import Band, EvidenceItem, Strength, score_posterior
from unravel.evidence import (
    VariantKey,
    acmg_items_from_row,
    build_evidence_ledger,
)


def _codes(items):
    return {i.code: i for i in items}


# --- gnomAD frequency mapping --------------------------------------------------


def test_absent_from_gnomad_is_pm2_supporting():
    items = _codes(acmg_items_from_row({"gnomad_af": None}))
    assert "PM2" in items
    assert items["PM2"].effective_strength is Strength.SUPPORTING


def test_ultra_rare_is_pm2():
    assert "PM2" in _codes(acmg_items_from_row({"gnomad_af": 2e-6}))


def test_common_is_ba1():
    assert "BA1" in _codes(acmg_items_from_row({"gnomad_af": 0.12}))


def test_one_percent_is_bs1():
    assert "BS1" in _codes(acmg_items_from_row({"gnomad_af": 0.02}))


def test_intermediate_frequency_has_no_criterion():
    items = _codes(acmg_items_from_row({"gnomad_af": 0.001}))
    assert not (items.keys() & {"PM2", "BS1", "BA1"})


# --- AlphaMissense mapping -----------------------------------------------------


def test_alphamissense_strong_pathogenic():
    items = _codes(acmg_items_from_row({"am_pathogenicity": 1.0, "am_class": "likely_pathogenic"}))
    assert items["PP3"].effective_strength is Strength.STRONG


def test_alphamissense_supporting_pathogenic():
    items = _codes(acmg_items_from_row({"am_pathogenicity": 0.6, "am_class": "likely_pathogenic"}))
    assert items["PP3"].effective_strength is Strength.SUPPORTING


def test_alphamissense_benign():
    assert "BP4" in _codes(acmg_items_from_row({"am_pathogenicity": 0.1, "am_class": "likely_benign"}))


def test_alphamissense_ambiguous_not_met():
    items = _codes(acmg_items_from_row({"am_pathogenicity": 0.45, "am_class": "ambiguous"}))
    assert not (items.keys() & {"PP3", "BP4"})


# --- the demo bridge: real 1-star trap numbers ---------------------------------

# MLH1 37004412 C>G in the live view: 1-star, absent from gnomAD, AlphaMissense 1.0.
TRAP_ROW = {
    "gene_symbol": "MLH1",
    "gnomad_af": None,
    "am_pathogenicity": 1.0,
    "am_class": "likely_pathogenic",
    "review_status": "criteria provided, single submitter",
    "review_stars": 1,
    "clinical_significance": "Uncertain significance",
    "number_submitters": 1,
}
KEY = VariantKey("3", 37004412, "C", "G")


def test_trap_ledger_is_uncertain_and_withheld():
    ctx = build_evidence_ledger(KEY, row=TRAP_ROW)
    assert ctx.found and ctx.gene_symbol == "MLH1"
    assert ctx.review_stars == 1
    result = score_posterior(ctx.ledger)
    # PM2 (+1) + PP3_Strong (+4) = 5 points: warm, but below the actionable line.
    assert result.points == 5
    assert result.band is Band.UNCERTAIN
    assert not result.is_actionable


def test_family_segregation_tips_trap_over():
    seg = EvidenceItem("PP1", source="pedigree", strength=Strength.STRONG,
                       detail="co-segregates in affected relatives")
    ctx = build_evidence_ledger(KEY, row=TRAP_ROW, extra=[seg])
    result = score_posterior(ctx.ledger)
    assert result.points == 9
    assert result.band is Band.LIKELY_PATHOGENIC
    assert result.is_actionable


def test_missing_variant_returns_not_found(monkeypatch):
    # Warehouse miss AND live miss -> genuinely not found. Mock the live path so
    # the unit test stays offline.
    import unravel.live_evidence as live
    monkeypatch.setattr(live, "fetch_live_row", lambda key: None)
    ctx = build_evidence_ledger(VariantKey("3", 1, "A", "T"), row=None,
                                client=_NoClient())
    assert not ctx.found
    assert ctx.source == "live"  # we did attempt the live fallback


def test_warehouse_miss_falls_back_to_live(monkeypatch):
    # An out-of-coverage variant (warehouse miss) is served live from the public
    # commons, tagged with provenance, and scores through the same engine.
    import unravel.live_evidence as live
    monkeypatch.setattr(live, "fetch_live_row", lambda key: {
        "gene_symbol": "BRCA1", "clinical_significance": "Likely pathogenic",
        "review_stars": 2, "gnomad_af": None,
        "am_pathogenicity": 0.93, "am_class": "likely_pathogenic",
        "consequence": "missense_variant", "sift_prediction": "deleterious",
    })
    ctx = build_evidence_ledger(VariantKey("17", 43063930, "G", "A"), row=None,
                                client=_NoClient())
    assert ctx.found
    assert ctx.source == "live"
    assert ctx.gene_symbol == "BRCA1"
    assert any(i.code == "PP3" for i in ctx.ledger.items)


class _NoClient:
    """Stub BigQuery client that finds nothing, for the not-found path."""

    def query(self, *a, **k):
        return self

    def result(self):
        return []
