"""Tests for the calibrated Bayesian ACMG engine.

Two things are proven here. First, the math is calibrated: a point total maps to
the posterior probability the ACMG/AMP Bayesian framework requires, and the
ClinGen point thresholds land on the right bands. Second, the demo beats hold in
code: the lone 1-star ClinVar assertion (the trap) stays below the actionable
line and is withheld, while the corroborated 3-star reclassification crosses it,
and a single next-best experiment (sister segregation) is what tips a warm
variant over.
"""

import math

import pytest

from unravel.acmg import (
    ACTIONABLE_POINTS,
    PRIOR_P,
    Band,
    EvidenceItem,
    Ledger,
    Strength,
    classify,
    posterior_at,
    score_posterior,
)


# --- calibration anchors -------------------------------------------------------


def test_zero_points_returns_prior():
    # No evidence either way: the posterior is exactly the prior.
    assert posterior_at(0) == pytest.approx(PRIOR_P)


def test_likely_pathogenic_threshold_is_about_90_percent():
    # 6 points is the Likely Pathogenic line; the framework puts it at ~0.90.
    assert posterior_at(6) == pytest.approx(0.90, abs=0.01)


def test_pathogenic_threshold_exceeds_99_percent():
    # 10 points is Pathogenic; posterior climbs above 0.99.
    assert posterior_at(10) > 0.99


def test_strong_benign_drives_posterior_to_near_zero():
    # 7 benign points (Benign band) collapses the posterior toward 0.
    assert posterior_at(-7) < 0.001


def test_posterior_is_monotonic_in_points():
    values = [posterior_at(p) for p in range(-10, 11)]
    assert values == sorted(values)
    assert all(0.0 < v < 1.0 for v in values)


# --- band thresholds (ClinGen 2020) --------------------------------------------


@pytest.mark.parametrize(
    "points, band",
    [
        (15, Band.PATHOGENIC),
        (10, Band.PATHOGENIC),
        (9, Band.LIKELY_PATHOGENIC),
        (6, Band.LIKELY_PATHOGENIC),
        (5, Band.UNCERTAIN),
        (0, Band.UNCERTAIN),
        (-1, Band.LIKELY_BENIGN),
        (-6, Band.LIKELY_BENIGN),
        (-7, Band.BENIGN),
        (-12, Band.BENIGN),
    ],
)
def test_classify_band_boundaries(points, band):
    assert classify(points) is band


# --- evidence items ------------------------------------------------------------


def test_default_strengths_and_signs():
    assert EvidenceItem("PVS1").points == 8
    assert EvidenceItem("PS3").points == 4
    assert EvidenceItem("PM2").points == 2
    assert EvidenceItem("PP3").points == 1
    assert EvidenceItem("BS1").points == -4
    assert EvidenceItem("BP4").points == -1


def test_strength_override():
    # ClinGen calibration can upgrade AlphaMissense PP3 to Strong (+4),
    # or down-weight a single functional assay to PS3_Moderate (+2).
    assert EvidenceItem("PP3", strength=Strength.STRONG).points == 4
    assert EvidenceItem("PS3", strength=Strength.MODERATE).points == 2


def test_not_met_contributes_zero():
    assert EvidenceItem("PVS1", met=False).points == 0


def test_unknown_code_rejected():
    with pytest.raises(ValueError):
        EvidenceItem("PX9")


def test_ba1_alone_is_benign():
    # BA1 stand-alone must land the variant in the Benign band on its own.
    result = score_posterior(Ledger("BA1-only").add("BA1", source="gnomAD v4"))
    assert result.band is Band.BENIGN
    assert result.posterior < 0.01


# --- scoring and citation ------------------------------------------------------


def test_score_sums_points_and_cites_only_met():
    ledger = (
        Ledger("demo")
        .add("PM2", source="gnomAD", detail="absent from population db")
        .add("PP3", source="AlphaMissense", strength=Strength.STRONG)
        .add("BP4", met=False, detail="considered, not met")
    )
    result = score_posterior(ledger)
    assert result.points == 2 + 4  # not-met BP4 excluded
    assert len(result.contributions) == 2
    assert all(c.code != "BP4" for c in result.contributions)
    assert result.cited_lines()  # renders without error


# --- the demo beats ------------------------------------------------------------


def _trap_ledger() -> Ledger:
    """The 1-star trap: a lone low-confidence pathogenic assertion with no
    corroborating primary evidence. Only rarity (PM2, down-weighted to
    supporting) is defensible."""
    return Ledger("MLH1:trap").add(
        "PM2",
        source="ClinVar 1-star, single submitter",
        detail="rare, but the assertion is low review status",
        strength=Strength.SUPPORTING,
    ).add("PP3", source="AlphaMissense", detail="ambiguous score", met=False)


def _warm_ledger() -> Ledger:
    """The corroborated variant just before the recommended experiment: rare
    plus a calibrated-strong in-silico signal, but still short of actionable."""
    return (
        Ledger("MLH1:c.demo")
        .add("PM2", source="gnomAD v4", detail="absent", strength=Strength.SUPPORTING)
        .add("PP3", source="AlphaMissense", detail="calibrated pathogenic", strength=Strength.STRONG)
    )


def test_one_star_trap_is_withheld():
    result = score_posterior(_trap_ledger())
    assert result.points < ACTIONABLE_POINTS
    assert not result.is_actionable
    assert result.band is Band.UNCERTAIN
    assert result.posterior < 0.90


def test_warm_variant_is_not_yet_actionable():
    result = score_posterior(_warm_ledger())
    assert result.points == 5
    assert not result.is_actionable
    assert result.points_to_actionable == 1


def test_segregation_tips_warm_variant_over_the_line():
    # The Resolution Planner's next-best-evidence call: sister co-segregation,
    # upgradeable to Strong, is the single move that makes the variant actionable.
    before = score_posterior(_warm_ledger())
    after = score_posterior(
        _warm_ledger().add(
            "PP1",
            source="pedigree",
            detail="co-segregates in affected sister",
            strength=Strength.STRONG,
        )
    )
    assert not before.is_actionable
    assert after.is_actionable
    assert after.band is Band.LIKELY_PATHOGENIC
    assert after.posterior > before.posterior


def test_three_star_corroborated_flip_is_actionable():
    """The real reclassification: multiple corroborating lines push the variant
    clearly past the actionable line to Pathogenic."""
    ledger = (
        Ledger("MLH1:flip")
        .add("PM2", source="gnomAD v4", detail="absent", strength=Strength.SUPPORTING)
        .add("PP3", source="AlphaMissense", detail="calibrated pathogenic", strength=Strength.STRONG)
        .add("PP1", source="pedigree", detail="segregation", strength=Strength.STRONG)
        .add("PS3", source="functional MMR assay", detail="MMR-deficient", strength=Strength.MODERATE)
    )
    result = score_posterior(ledger)
    assert result.is_actionable
    assert result.band is Band.PATHOGENIC
    assert result.posterior > 0.95
    assert result.points_to_actionable == 0
