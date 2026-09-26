"""Resolution Planner: rank the next experiment by information value.

The never-done core. When a variant is suggestive but short of actionable (the
withheld trap), the question is not "is it pathogenic?" but "what is the single
highest-yield experiment to resolve it?". This ranks candidate next steps in ACMG
currency: for each, it adds the evidence the experiment would yield to the current
ledger, recomputes the calibrated posterior, and reports the band it would reach.
The recommendation is the cheapest experiment that crosses the actionable line, or
failing that the one that moves the posterior most.

Deterministic and grounded: every candidate's projected posterior is the real
Bayesian math, not a guess. Feasibility and cost are clinical annotations so the
plan is a real next step a lab could act on.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .acmg import ACTIONABLE_POINTS, EvidenceItem, Strength, score_posterior
from .evidence import EvidenceContext


@dataclass(frozen=True)
class Candidate:
    label: str
    code: str
    strength: Strength
    detail: str
    feasibility: str       # how readily a lab can do this
    cost: int              # 1 cheap/fast .. 4 slow/expensive (for tie-breaks)


# Candidate experiments for a Lynch-gene missense VUS, with the ACMG evidence
# each would contribute if it came back supporting pathogenicity.
_CANDIDATES = [
    Candidate("Tumour MMR immunohistochemistry (IHC)", "PS3", Strength.MODERATE,
              "loss of MLH1/PMS2 staining supports a deleterious effect",
              "days, on existing FFPE block", 1),
    Candidate("Microsatellite instability (MSI) testing", "PS3", Strength.MODERATE,
              "MSI-high supports mismatch-repair deficiency", "days, on tumour DNA", 1),
    Candidate("Co-segregation in affected relatives", "PP1", Strength.STRONG,
              "variant tracks with disease across the pedigree", "weeks, needs relative testing", 3),
    Candidate("Functional MMR activity assay", "PS3", Strength.STRONG,
              "direct loss of repair activity in vitro", "weeks, specialist lab", 4),
    Candidate("RNA / splicing assay", "PP3", Strength.MODERATE,
              "aberrant splicing supports a damaging effect", "weeks, RNA from blood", 3),
]


@dataclass
class PlanStep:
    label: str
    code: str
    strength: str
    projected_points: int
    projected_posterior: float
    projected_band: str
    crosses_actionable: bool
    feasibility: str
    detail: str


@dataclass
class ResolutionPlan:
    variant: str
    current_points: int
    current_posterior: float
    current_band: str
    gap_to_actionable: int
    steps: list[PlanStep] = field(default_factory=list)
    recommendation: str = ""

    def as_dict(self) -> dict:
        return {
            "variant": self.variant,
            "current_points": self.current_points,
            "current_posterior": round(self.current_posterior, 4),
            "current_band": self.current_band,
            "gap_to_actionable": self.gap_to_actionable,
            "recommendation": self.recommendation,
            "steps": [vars(s) for s in self.steps],
        }


def plan_next_evidence(ctx: EvidenceContext) -> ResolutionPlan:
    """Rank candidate experiments by the posterior they would reach."""
    base = score_posterior(ctx.ledger)
    steps: list[PlanStep] = []
    for c in _CANDIDATES:
        # skip a candidate whose criterion is already in the ledger
        if any(i.code == c.code and i.met for i in ctx.ledger.items):
            continue
        trial = copy.deepcopy(ctx.ledger)
        trial.items.append(EvidenceItem(c.code, source="proposed experiment",
                                        detail=c.detail, strength=c.strength))
        res = score_posterior(trial)
        steps.append(PlanStep(
            label=c.label, code=c.code, strength=c.strength.name.title(),
            projected_points=res.points, projected_posterior=round(res.posterior, 4),
            projected_band=res.band.value,
            crosses_actionable=res.is_actionable, feasibility=c.feasibility, detail=c.detail,
        ))

    # rank: crossing the line first, then highest posterior, then cheapest/fastest
    cost = {c.label: c.cost for c in _CANDIDATES}
    steps.sort(key=lambda s: (not s.crosses_actionable, -s.projected_posterior, cost.get(s.label, 9)))

    rec = ""
    if steps:
        top = steps[0]
        if top.crosses_actionable:
            # among those that cross, the cheapest is the smart recommendation
            crossing = [s for s in steps if s.crosses_actionable]
            crossing.sort(key=lambda s: (cost.get(s.label, 9), -s.projected_posterior))
            best = crossing[0]
            rec = (f"{best.label} is the highest-yield next step: it would take the "
                   f"posterior to {best.projected_posterior:.2f} ({best.projected_band}), "
                   f"crossing the actionable line.")
        else:
            rec = (f"No single experiment crosses the actionable line; {top.label} moves "
                   f"the posterior furthest, to {top.projected_posterior:.2f}.")

    return ResolutionPlan(
        variant=base.variant,
        current_points=base.points,
        current_posterior=base.posterior,
        current_band=base.band.value,
        gap_to_actionable=max(0, ACTIONABLE_POINTS - base.points),
        steps=steps,
        recommendation=rec,
    )
