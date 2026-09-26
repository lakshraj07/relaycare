"""Tests for the Adjudicator's grounding and schema (no live LLM call).

The verdict quality itself is verified live via scripts/run_adjudication.py; here
we only check that the grounding prompt carries the facts the agent must weigh
(crucially the review status that separates the otherwise-identical HERO and TRAP
cases) and that the structured Verdict parses.
"""

from unravel.acmg import Band
from unravel.adjudicator import Verdict, build_adjudicator, grounding_prompt
from unravel.detection import Reclassification
from unravel.evidence import VariantKey, build_evidence_ledger


def _reclass(patient, gid, hgvs, current, stars):
    chrom, pos, ref, alt = gid.split("-")
    return Reclassification(
        patient_id=patient, gene="MLH1", hgvs_c=hgvs,
        variant=VariantKey(chrom, int(pos), ref, alt),
        recorded_class="Uncertain significance", recorded_date="2019-03-15",
        current_class=current, review_stars=stars, last_evaluated="Jun 16, 2023",
        direction="escalation",
    )


HERO_ROW = {"gene_symbol": "MLH1", "gnomad_af": None,
            "am_pathogenicity": 1.0, "am_class": "likely_pathogenic"}


def test_grounding_carries_review_status_and_cited_evidence():
    r = _reclass("diane-marchetti", "3-36993661-C-G", "c.114C>G", "Pathogenic", 3)
    ctx = build_evidence_ledger(r.variant, row=HERO_ROW)
    prompt = grounding_prompt(r, ctx)
    assert "3-star" in prompt
    assert "Pathogenic" in prompt
    assert "PM2" in prompt and "PP3" in prompt
    assert "0.81" in prompt  # the deterministic posterior is handed to the agent


def test_hero_and_trap_grounding_differ_only_in_review_status():
    hero = _reclass("diane-marchetti", "3-36993661-C-G", "c.114C>G", "Pathogenic", 3)
    trap = _reclass("eric-larsson", "3-37001040-G-A", "c.293G>A",
                    "Conflicting classifications of pathogenicity", 1)
    ph = grounding_prompt(hero, build_evidence_ledger(hero.variant, row=HERO_ROW))
    pt = grounding_prompt(trap, build_evidence_ledger(trap.variant, row=HERO_ROW))
    # same molecular posterior in both
    assert "0.81" in ph and "0.81" in pt
    # the distinguishing fact
    assert "3-star" in ph and "1-star" in pt
    assert "Conflicting" in pt


def test_verdict_schema_parses():
    v = Verdict.model_validate_json(
        '{"triage":"actionable","action":"draft_recontact","withheld":false,'
        '"rationale":"3-star expert panel Pathogenic corroborated by PM2 and PP3.",'
        '"key_evidence":["3-star expert panel","PM2","PP3"]}')
    assert v.triage == "actionable"
    assert not v.withheld


def test_adjudicator_agent_is_structured():
    agent = build_adjudicator()
    assert agent.output_schema is Verdict
    assert "pro" in agent.model
