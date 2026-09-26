"""Evaluate the AI, not the deterministic diff (the test that actually matters).

The detection backtest exercises a deterministic category diff, which is correct
by construction and proves nothing about intelligence. The hard, non-trivial part
of Unravel is the Gemini Pro Adjudicator's JUDGEMENT: given molecular evidence
that is identical across cases, does it correctly withhold on a low-confidence
(1-star / conflicting) review and act on a high-confidence (3-star expert-panel)
review, and reassure on a benign downgrade?

This harness runs the LIVE Adjudicator over a balanced set of cases where the
molecular posterior is held roughly constant and only the review quality and
direction vary, so the only thing the model can be scoring on is the clinical
judgement. It is the "arithmetically identical, opposite verdict" claim, tested
at sample scale instead of on a single demo pair.

Costs Gemini Pro tokens; run on demand:
  cd backend && PYTHONPATH=. .venv/bin/python eval/adjudicator_eval.py --n 12

Writes eval/adjudicator_eval.md.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # Vertex config

from unravel.acmg import Ledger, Strength, score_posterior  # noqa: E402
from unravel.adjudicator import adjudicate, build_adjudicator  # noqa: E402
from unravel.detection import Reclassification  # noqa: E402
from unravel.evidence import EvidenceContext, VariantKey  # noqa: E402

OUT_MD = Path(__file__).resolve().parent / "adjudicator_eval.md"


def _ledger(kind: str) -> Ledger:
    led = Ledger()
    if kind == "escalation":
        # the demo's "identical molecular evidence": absent + AlphaMissense-strong
        led.add("PM2", source="gnomAD v4", detail="absent from gnomAD", strength=Strength.SUPPORTING)
        led.add("PP3", source="AlphaMissense", detail="am_pathogenicity 0.99", strength=Strength.STRONG)
    elif kind == "downgrade":
        led.add("BA1", source="gnomAD v4", detail="allele frequency 0.061 (>5%)")
    return led


def _case(pid, gene, hgvs, stars, current_class, direction, kind, expect):
    led = _ledger(kind)
    key = VariantKey("1", 1000 + len(pid), "C", "T")
    reclass = Reclassification(
        patient_id=pid, gene=gene, hgvs_c=hgvs, variant=key,
        recorded_class="Uncertain significance", recorded_date="2018-01-01",
        current_class=current_class, review_stars=stars,
        last_evaluated="2024-01-01", direction=direction)
    ctx = EvidenceContext(ledger=led, gene_symbol=gene, clinical_significance=current_class,
                          review_stars=stars)
    return {"reclass": reclass, "ctx": ctx, "expect": expect,
            "label": f"{gene} {hgvs} | {stars}star {direction}"}


def build_cases() -> list[dict]:
    """Balanced: high-confidence escalations (act), low-confidence escalations
    (withhold), benign downgrades (reassure). Same molecular evidence across the
    two escalation arms, only the review quality differs."""
    cases = []
    hi = [("MLH1", "c.114C>G"), ("MSH2", "c.1A>G"), ("BRCA1", "c.181T>G"), ("TP53", "c.733G>A")]
    lo = [("MLH1", "c.293G>A"), ("MSH6", "c.10C>T"), ("PMS2", "c.137G>T"), ("APC", "c.3920T>A")]
    dn = [("CHEK2", "c.470T>C"), ("ATM", "c.6919C>T"), ("PALB2", "c.1A>C"), ("BRCA2", "c.865A>C")]
    for i, (g, h) in enumerate(hi):
        cases.append(_case(f"hi{i}", g, h, 3, "Pathogenic", "escalation", "escalation", "act"))
    for i, (g, h) in enumerate(lo):
        cases.append(_case(f"lo{i}", g, h, 1, "Conflicting classifications of pathogenicity",
                          "escalation", "escalation", "withhold"))
    for i, (g, h) in enumerate(dn):
        cases.append(_case(f"dn{i}", g, h, 3, "Benign", "downgrade", "downgrade", "reassure"))
    return cases


def score(expect: str, verdict) -> bool:
    if expect == "withhold":
        return bool(verdict.withheld)
    if expect == "act":
        return (not verdict.withheld) and verdict.action == "draft_recontact"
    if expect == "reassure":
        return verdict.action == "reassure_downgrade"
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="number of cases to run (max 12)")
    args = ap.parse_args()

    cases = build_cases()[: args.n]
    agent = build_adjudicator()
    rows, correct = [], 0
    by_arm: dict[str, list[int]] = {"act": [0, 0], "withhold": [0, 0], "reassure": [0, 0]}

    for c in cases:
        post = score_posterior(c["ctx"].ledger)
        try:
            adj = adjudicate(c["reclass"], c["ctx"], agent=agent)
            v = adj.verdict
            ok = score(c["expect"], v)
        except Exception as e:
            rows.append((c["label"], c["expect"], f"ERROR {type(e).__name__}", False, post.posterior))
            by_arm[c["expect"]][1] += 1
            continue
        correct += int(ok)
        by_arm[c["expect"]][0] += int(ok)
        by_arm[c["expect"]][1] += 1
        rows.append((c["label"], c["expect"],
                     f"{v.triage}/{v.action}{' WITHHELD' if v.withheld else ''}", ok, post.posterior))
        print(f"  [{'OK ' if ok else 'XX '}] {c['label']:32} post {post.posterior:.2f} "
              f"expect {c['expect']:9} -> {v.triage}/{v.action}{' WITHHELD' if v.withheld else ''}")

    n = len(cases)
    acc = correct / n if n else 0.0
    print(f"\nAdjudicator decision accuracy: {correct}/{n} = {acc:.2f}")
    for arm, (c_ok, c_tot) in by_arm.items():
        if c_tot:
            print(f"  {arm:9}: {c_ok}/{c_tot}")

    table = "\n".join(
        f"| {label} | {exp} | {got} | {'correct' if ok else 'WRONG'} |"
        for label, exp, got, ok, _ in rows)
    md = f"""# Adjudicator (AI) Evaluation, the test that matters

*Generated by `eval/adjudicator_eval.py` (live Gemini 3.1 Pro). Unlike the
deterministic detection backtest, this scores the probabilistic agent's judgement.*

The molecular evidence is held roughly constant; only the ClinVar review quality
and the direction vary. The model is given the clinical principle but not the
answer for any case. A pass means it withheld on the low-confidence (1-star /
conflicting) escalations, acted on the high-confidence (3-star expert-panel)
escalations, and reassured on the benign downgrades, the "arithmetically
identical, opposite verdict" claim, at sample scale rather than on one demo pair.

**Decision accuracy: {correct}/{n} = {acc:.2f}**

| Case | Expected | Adjudicator verdict | Result |
|---|---|---|---|
{table}

Per arm: """ + ", ".join(f"{arm} {c_ok}/{c_tot}" for arm, (c_ok, c_tot) in by_arm.items() if c_tot) + """

**What this does and does not show (honest).** The Adjudicator is *instructed* on
the clinical principle (a 3-4 star review can justify acting; a 1-star/conflicting
assertion must be withheld; a benign move is reassurance). So this measures whether
the probabilistic agent **reliably applies that reasoning** across varied inputs and
makes the identical-posterior discrimination a threshold cannot, not that it
*discovered* the rule unaided. That reliable application is still non-trivial for an
LLM (it must parse the grounding, weigh it, and emit a correct structured verdict,
any of which it could get wrong) and is the genuine test of the moat, unlike the
deterministic detection/action scores, which are correct by construction. The live
model is stochastic, so this is one sample; re-run for a fresh draw.
"""
    OUT_MD.write_text(md)
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
