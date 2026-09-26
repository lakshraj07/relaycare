"""The calibrated Bayesian ACMG evidence engine, Unravel's science spine.

This module turns a ledger of cited ACMG/AMP evidence into a *calibrated
probability of pathogenicity*, so the VUS meter shows a real posterior rather
than a vibe. The math is the point-based Bayesian formulation of the ACMG/AMP
guidelines:

  - Tavtigian et al. 2018 (Genet Med), "Modeling the ACMG/AMP variant
    classification guidelines as a Bayesian classification framework", which
    fixes a prior probability of pathogenicity and an odds of pathogenicity for
    a single "Very Strong" line of evidence.
  - Tavtigian et al. 2020 (Genet Med), "Fitting a naturally scaled point system
    to the ACMG/AMP variant classification guidelines", which shows the same
    framework collapses to a simple additive point score whose thresholds line
    up with the qualitative ACMG categories.

The two papers agree on the constants used below: Prior_P = 0.10 and an odds of
pathogenicity for one Very Strong criterion of 350:1. Every evidence strength is
a power of that odds, and equivalently a number of points:

    Supporting  = Odds_PVSt ** (1/8)  = 1 point
    Moderate    = Odds_PVSt ** (2/8)  = 2 points
    Strong      = Odds_PVSt ** (4/8)  = 4 points
    Very Strong = Odds_PVSt ** (8/8)  = 8 points

Benign evidence carries the same magnitudes with a negative sign. Summing the
points gives a combined odds (C ** points, where C = Odds_PVSt ** (1/8)) and the
posterior follows directly from Bayes' rule. The ClinGen point thresholds then
fall out as posterior bands (Likely Pathogenic at 6 points is ~0.90, Pathogenic
at 10 points is ~0.99, and so on).

This is deliberately pure, deterministic plumbing: it computes a probability
from evidence the Adjudicator has already decided to admit. The clinical
judgment (which evidence to trust, when to withhold) lives in the agent layer;
this module just makes that judgment quantitative and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --- Bayesian calibration constants (Tavtigian 2018) ---------------------------

PRIOR_P = 0.10
"""Prior probability that a variant reaching classification is pathogenic."""

ODDS_PVST = 350.0
"""Odds of pathogenicity contributed by one Very Strong line of evidence."""

# Odds multiplier per ACMG point. One point == Supporting == Odds_PVSt ** (1/8).
C = ODDS_PVST ** (1.0 / 8.0)


class Strength(Enum):
    """ACMG evidence strength, valued as its signed point weight.

    Magnitudes follow the point system (Supporting 1, Moderate 2, Strong 4,
    Very Strong 8). STAND_ALONE is BA1's stand-alone benign weight: large enough
    that a single BA1 lands the variant in the Benign band on its own, which is
    how the qualitative rule behaves.
    """

    VERY_STRONG = 8
    STRONG = 4
    MODERATE = 2
    SUPPORTING = 1
    STAND_ALONE = 8  # only used on the benign side (BA1); sign applied at scoring


class Direction(Enum):
    PATHOGENIC = 1
    BENIGN = -1


# --- ACMG criteria catalogue ---------------------------------------------------

# code -> (direction, default strength). Strength can be overridden per evidence
# item (e.g. ClinGen recommends AlphaMissense as PP3 at up to Strong; functional
# assays are often down-weighted to PS3_Moderate). Overrides are how the
# Adjudicator's calibrated weighting enters the math.
_CRITERIA: dict[str, tuple[Direction, Strength]] = {
    # Pathogenic, very strong
    "PVS1": (Direction.PATHOGENIC, Strength.VERY_STRONG),
    # Pathogenic, strong
    "PS1": (Direction.PATHOGENIC, Strength.STRONG),
    "PS2": (Direction.PATHOGENIC, Strength.STRONG),
    "PS3": (Direction.PATHOGENIC, Strength.STRONG),
    "PS4": (Direction.PATHOGENIC, Strength.STRONG),
    # Pathogenic, moderate
    "PM1": (Direction.PATHOGENIC, Strength.MODERATE),
    "PM2": (Direction.PATHOGENIC, Strength.MODERATE),
    "PM3": (Direction.PATHOGENIC, Strength.MODERATE),
    "PM4": (Direction.PATHOGENIC, Strength.MODERATE),
    "PM5": (Direction.PATHOGENIC, Strength.MODERATE),
    "PM6": (Direction.PATHOGENIC, Strength.MODERATE),
    # Pathogenic, supporting
    "PP1": (Direction.PATHOGENIC, Strength.SUPPORTING),
    "PP2": (Direction.PATHOGENIC, Strength.SUPPORTING),
    "PP3": (Direction.PATHOGENIC, Strength.SUPPORTING),
    "PP4": (Direction.PATHOGENIC, Strength.SUPPORTING),
    "PP5": (Direction.PATHOGENIC, Strength.SUPPORTING),
    # Benign, stand-alone
    "BA1": (Direction.BENIGN, Strength.STAND_ALONE),
    # Benign, strong
    "BS1": (Direction.BENIGN, Strength.STRONG),
    "BS2": (Direction.BENIGN, Strength.STRONG),
    "BS3": (Direction.BENIGN, Strength.STRONG),
    "BS4": (Direction.BENIGN, Strength.STRONG),
    # Benign, supporting
    "BP1": (Direction.BENIGN, Strength.SUPPORTING),
    "BP2": (Direction.BENIGN, Strength.SUPPORTING),
    "BP3": (Direction.BENIGN, Strength.SUPPORTING),
    "BP4": (Direction.BENIGN, Strength.SUPPORTING),
    "BP5": (Direction.BENIGN, Strength.SUPPORTING),
    "BP6": (Direction.BENIGN, Strength.SUPPORTING),
    "BP7": (Direction.BENIGN, Strength.SUPPORTING),
}


def known_codes() -> tuple[str, ...]:
    """All ACMG criterion codes the engine understands."""
    return tuple(_CRITERIA)


# --- Classification bands (ClinGen point thresholds) ---------------------------


class Band(Enum):
    PATHOGENIC = "Pathogenic"
    LIKELY_PATHOGENIC = "Likely pathogenic"
    UNCERTAIN = "Uncertain significance"
    LIKELY_BENIGN = "Likely benign"
    BENIGN = "Benign"


# Lowest point total that counts as clinically actionable (Likely Pathogenic).
ACTIONABLE_POINTS = 6


def classify(points: int) -> Band:
    """Map a signed point total to its ACMG band (Tavtigian 2020 thresholds)."""
    if points >= 10:
        return Band.PATHOGENIC
    if points >= 6:
        return Band.LIKELY_PATHOGENIC
    if points >= 0:
        return Band.UNCERTAIN
    if points >= -6:
        return Band.LIKELY_BENIGN
    return Band.BENIGN


def posterior_at(points: int | float) -> float:
    """Calibrated posterior probability of pathogenicity for a point total.

    Combined odds is C ** points; Bayes' rule converts prior + odds to a
    posterior. At 0 points this returns the prior (0.10).
    """
    odds = C ** points
    return (odds * PRIOR_P) / ((odds - 1.0) * PRIOR_P + 1.0)


# --- Evidence ledger -----------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    """One cited line of ACMG evidence.

    code:     ACMG criterion (e.g. "PM2", "PP3", "BS1").
    source:   where it came from, for provenance (e.g. "gnomAD v4", "AlphaMissense").
    detail:   human-readable rationale shown in the cited ledger.
    strength: optional override of the criterion's default strength, e.g.
              Strength.STRONG for a ClinGen-calibrated AlphaMissense PP3, or
              Strength.MODERATE to down-weight a single functional assay (PS3).
    met:      False records a criterion that was considered but not met (it
              contributes zero points but stays visible in the trajectory).
    """

    code: str
    source: str = ""
    detail: str = ""
    strength: Strength | None = None
    met: bool = True

    def __post_init__(self) -> None:
        if self.code not in _CRITERIA:
            raise ValueError(
                f"unknown ACMG code {self.code!r}; known codes: "
                f"{', '.join(known_codes())}"
            )

    @property
    def direction(self) -> Direction:
        return _CRITERIA[self.code][0]

    @property
    def effective_strength(self) -> Strength:
        return self.strength or _CRITERIA[self.code][1]

    @property
    def points(self) -> int:
        """Signed point contribution (0 if not met)."""
        if not self.met:
            return 0
        return self.direction.value * self.effective_strength.value


@dataclass
class Ledger:
    """A variant's assembled ACMG evidence."""

    variant: str = ""
    items: list[EvidenceItem] = field(default_factory=list)

    def add(
        self,
        code: str,
        source: str = "",
        detail: str = "",
        strength: Strength | None = None,
        met: bool = True,
    ) -> "Ledger":
        """Append an evidence item; returns self for chaining."""
        self.items.append(EvidenceItem(code, source, detail, strength, met))
        return self


# --- Result --------------------------------------------------------------------


@dataclass(frozen=True)
class Contribution:
    code: str
    points: int
    source: str
    detail: str


@dataclass(frozen=True)
class PosteriorResult:
    """The calibrated verdict, with everything needed to cite it."""

    variant: str
    points: int
    posterior: float
    band: Band
    contributions: tuple[Contribution, ...]
    prior: float = PRIOR_P

    @property
    def is_actionable(self) -> bool:
        """Likely Pathogenic or Pathogenic (the recontact-worthy bands)."""
        return self.points >= ACTIONABLE_POINTS

    @property
    def points_to_actionable(self) -> int:
        """Additional pathogenic points needed to reach the actionable line.

        Zero once actionable. This is the raw input to the gap-to-actionable
        display and the Resolution Planner's information-value ranking.
        """
        return max(0, ACTIONABLE_POINTS - self.points)

    def cited_lines(self) -> list[str]:
        """One human-readable line per met criterion, for the evidence panel."""
        lines = []
        for c in self.contributions:
            sign = "+" if c.points >= 0 else ""
            src = f" [{c.source}]" if c.source else ""
            note = f": {c.detail}" if c.detail else ""
            lines.append(f"{c.code} {sign}{c.points}{src}{note}")
        return lines


def score_posterior(ledger: Ledger) -> PosteriorResult:
    """Compute the calibrated posterior for an assembled evidence ledger.

    Sums the signed ACMG points, converts to a posterior probability via the
    Bayesian framework, and assigns the ClinGen band. Every met criterion is
    returned as a Contribution so the verdict can cite its evidence. Criteria
    recorded as not met contribute nothing and are omitted from the citation.
    """
    contributions = tuple(
        Contribution(it.code, it.points, it.source, it.detail)
        for it in ledger.items
        if it.met
    )
    points = sum(c.points for c in contributions)
    return PosteriorResult(
        variant=ledger.variant,
        points=points,
        posterior=posterior_at(points),
        band=classify(points),
        contributions=contributions,
    )


def posterior_breakdown(ledger: Ledger) -> dict:
    """The transparent points -> odds -> posterior waterfall for a ledger.

    Shows exactly "what goes into what": starting from the prior, each cited
    evidence item moves the running point total, the combined odds, and the
    posterior. This is what the UI renders so a judge can watch a verdict build
    from evidence rather than appear as a number. Pure; mirrors `score_posterior`.
    """
    result = score_posterior(ledger)
    steps: list[dict] = []
    cumulative = 0
    for c in result.contributions:
        cumulative += c.points
        steps.append({
            "code": c.code,
            "points": c.points,
            "source": c.source,
            "detail": c.detail,
            "cumulative_points": cumulative,
            "cumulative_posterior": round(posterior_at(cumulative), 4),
        })
    return {
        "variant": result.variant,
        "prior": PRIOR_P,
        "prior_posterior": round(posterior_at(0), 4),
        "steps": steps,
        "total_points": result.points,
        "odds_path": round(C ** result.points, 3),
        "posterior": round(result.posterior, 4),
        "band": result.band.value,
        "points_to_actionable": result.points_to_actionable,
        "is_actionable": result.is_actionable,
        "actionable_line": {
            "points": ACTIONABLE_POINTS,
            "posterior": round(posterior_at(ACTIONABLE_POINTS), 4),
        },
    }
