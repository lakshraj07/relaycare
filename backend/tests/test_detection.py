"""Tests for detect_reclassifications and match_affected_patients.

Driven by injected registry data and a fake current-classification map, so no
Firestore or BigQuery is needed.
"""

from unravel import registry
from unravel.detection import detect_reclassifications


def _data():
    return registry.build_resources()


def _current_for(data):
    """A current-classification map matching the seeded demo intent."""
    # gid -> (clinical_significance, clin_sig_simple, stars)
    now = {
        registry.HERO.gid: ("Pathogenic", 1, 3),
        registry.TRAP.gid: ("Conflicting classifications of pathogenicity", 1, 1),
        registry.MSH2_LP.gid: ("Likely pathogenic", 1, 3),
        registry.MLH1_BENIGN.gid: ("Benign", 0, 3),
        registry.MSH6_BENIGN.gid: ("Benign", 0, 3),
        registry.EPCAM_BENIGN.gid: ("Benign", 0, 2),
    }
    return {gid: {"clinical_significance": s, "clin_sig_simple": cs,
                  "review_stars": st, "last_evaluated": "Jun 16, 2023"}
            for gid, (s, cs, st) in now.items()}


def test_detects_hero_and_silent_dianes_as_escalations():
    data = _data()
    dets = detect_reclassifications(data=data, current=_current_for(data))
    hero_escalations = [d for d in dets
                        if d.variant == registry.HERO.key and d.is_escalation]
    assert {d.patient_id for d in hero_escalations} == {"diane-marchetti", "mei-tanaka"}


def test_downgrade_is_flagged_but_not_escalation():
    data = _data()
    dets = detect_reclassifications(data=data, current=_current_for(data))
    kemi = next(d for d in dets if d.patient_id == "grace-mensah")
    assert kemi.direction == "downgrade"
    assert not kemi.is_escalation


def test_untested_relatives_not_flagged():
    # At-risk relatives carry no Observation, so they are never flagged as
    # reclassifications; only the tested carriers are.
    data = _data()
    dets = detect_reclassifications(data=data, current=_current_for(data))
    flagged = {d.patient_id for d in dets}
    assert flagged == {"diane-marchetti", "mei-tanaka", "thomas-nguyen",
                       "eric-larsson", "grace-mensah"}
    for relative in ("laura-marchetti", "kenji-tanaka", "naomi-mensah", "anna-larsson"):
        assert relative not in flagged


def test_trap_is_detected_for_the_adjudicator_to_withhold():
    data = _data()
    dets = detect_reclassifications(data=data, current=_current_for(data))
    john = next(d for d in dets if d.patient_id == "eric-larsson")
    assert john.is_escalation
    assert john.review_stars == 1  # low confidence: the Adjudicator will withhold


def test_since_filters_out_records_newer_than_floor():
    data = _data()
    # Diane's record is 2019-03-15; a 2015 floor means her record is NOT stale.
    dets = detect_reclassifications(since="2015-01-01", data=data, current=_current_for(data))
    assert "diane-marchetti" not in {d.patient_id for d in dets}
    # Thomas's record is 2015-04-10 > 2015-01-01, also excluded.
    assert "thomas-nguyen" not in {d.patient_id for d in dets}


def test_match_affected_patients_returns_carriers_and_relatives():
    data = _data()
    m = registry.match_affected_patients(registry.HERO.key, data=data)
    assert {c["patient"]["id"] for c in m["carriers"]} == {"diane-marchetti", "mei-tanaka"}
    # both carriers' at-risk relatives are surfaced for the cascade
    assert {r["patient"]["id"] for r in m["relatives"]} == {
        "sofia-marchetti", "marco-marchetti", "laura-marchetti",
        "kenji-tanaka", "aiko-tanaka"}


def test_match_includes_deceased_carrier_flag():
    data = _data()
    m = registry.match_affected_patients(registry.MSH2_LP.key, data=data)
    samuel = next(c for c in m["carriers"] if c["patient"]["id"] == "thomas-nguyen")
    assert samuel["deceased"] is True
