"""The Adjudicator: Unravel's grounded, cited verdict on a reclassification.

This is the moat. Detection and the posterior are plumbing; the hard call is
clinical judgment over discordant, uneven-quality evidence, and that is what a
Gemini 3.1 Pro agent does here. It receives a variant whose registry record may
be stale, the evidence assembled from the commons (every line cited with its
ACMG criterion and source), and the calibrated posterior computed from that
evidence, then decides the triage and the next action, and cites why.

Why an LLM and not a threshold: the two demo cases are arithmetically identical.
Diane's MLH1 c.114C>G and the trap MLH1 c.293G>A are both absent from gnomAD and
scored 1.0 by AlphaMissense, so both carry the same ~5-point molecular posterior.
What separates them is review quality: Diane's variant is now a 3-star expert
panel Pathogenic (a completed expert ACMG review), while the trap is a 1-star,
conflicting assertion. A rule on the posterior cannot tell them apart; grounded
reasoning over the review status can. That is the withhold beat, and it is an AI
judgment narrated over cited evidence, not a hard-coded rule.

The posterior itself stays deterministic (score_posterior); the agent is given it
as a grounding fact and must not invent numbers. The agent never sends anything:
its output is a draft verdict for a clinician.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from .acmg import PosteriorResult, score_posterior
from .agent import MODEL_PRO
from .detection import Reclassification
from .evidence import EvidenceContext

APP = "unravel-adjudicator"


class Verdict(BaseModel):
    """The Adjudicator's grounded decision (structured output)."""

    triage: Literal["cold", "warm", "hot", "actionable"] = Field(
        description="Clinical heat: cold (benign/no concern), warm (uncertain, "
        "watch), hot (suggestive, not yet sufficient), actionable (sufficient to "
        "draft clinician-gated recontact).")
    action: Literal[
        "draft_recontact", "withhold_pending_review",
        "recommend_next_evidence", "reassure_downgrade",
    ] = Field(description="The single next step.")
    withheld: bool = Field(
        description="True if escalation to family recontact is deliberately held "
        "back despite suggestive evidence (e.g. low review confidence).")
    rationale: str = Field(
        description="2-4 sentences of clinical reasoning that weighs the evidence "
        "and the review status, and justifies the triage and action. Cite the "
        "ACMG criteria and review status you relied on. No invented evidence.")
    key_evidence: list[str] = Field(
        description="The specific cited lines or facts that drove the decision.")


@dataclass
class Adjudication:
    """Deterministic posterior plus the agent's grounded verdict."""

    reclassification: Reclassification
    posterior: PosteriorResult
    verdict: Verdict


_INSTRUCTION = (
    "You are the Unravel Adjudicator, a clinical molecular geneticist reviewing a "
    "variant whose classification in a clinic's patient registry may be out of "
    "date. You are given the current evidence assembled from the public commons "
    "(each line cited with its ACMG/AMP criterion and source), the ClinVar review "
    "status, and a calibrated posterior probability of pathogenicity computed from "
    "the molecular evidence. Reason like a variant scientist.\n\n"
    "Principles:\n"
    "- Cite only the evidence you are given; never invent findings or numbers. The "
    "posterior is computed for you; treat it as fact.\n"
    "- Weigh review quality. A 3-4 star classification (reviewed by expert panel or "
    "practice guideline) reflects a completed expert ACMG review and, when "
    "corroborated by the molecular evidence, can justify an actionable verdict even "
    "if the molecular-only posterior sits in the uncertain band. A 1-star or "
    "'conflicting classifications' assertion is low-confidence: suggestive "
    "molecular evidence alone must NOT drive family recontact. In that case "
    "withhold and recommend the highest-yield next evidence.\n"
    "- A move to benign is reassurance (reassure_downgrade), not an alarm.\n"
    "- You never contact a patient. Every output is a draft for a clinician to "
    "review and send. Be precise and clinical."
)


def _grounding(adj_input: "AdjudicationInput") -> str:
    r, ctx, post = adj_input.reclass, adj_input.context, adj_input.posterior
    lines = [
        f"VARIANT: {r.gene} {r.hgvs_c} ({r.variant.label()})",
        f"REGISTRY: recorded \"{r.recorded_class}\" on {r.recorded_date} "
        f"(patient {r.patient_id})",
        f"CURRENT ClinVar: \"{r.current_class}\", review status "
        f"{r.review_stars}-star; last evaluated {r.last_evaluated}",
        f"DIRECTION since the registry record: {r.direction}",
        f"CALIBRATED POSTERIOR (molecular evidence only): "
        f"{post.posterior:.2f} probability pathogenic, {post.points} ACMG points, "
        f"band \"{post.band.value}\"; {post.points_to_actionable} point(s) from the "
        f"actionable line.",
        "CITED EVIDENCE LEDGER:",
    ]
    lines += [f"  - {line}" for line in post.cited_lines()] or ["  (no molecular criteria met)"]
    if adj_input.freshness:
        lines.append(f"DATA FRESHNESS: {adj_input.freshness}")
    lines.append("\nAdjudicate: give the triage, the single next action, whether "
                 "you are withholding, and a cited rationale.")
    return "\n".join(lines)


@dataclass
class AdjudicationInput:
    reclass: Reclassification
    context: EvidenceContext
    posterior: PosteriorResult
    freshness: str | None = None


def build_adjudicator() -> LlmAgent:
    return LlmAgent(
        name="unravel_adjudicator",
        model=MODEL_PRO,
        description="Grounded, cited verdict on a variant reclassification.",
        instruction=_INSTRUCTION,
        output_schema=Verdict,
        output_key="verdict",
    )


async def _run_agent(agent: LlmAgent, prompt: str) -> str:
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP, session_service=session_service)
    await session_service.create_session(app_name=APP, user_id="adj", session_id="s")
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    final = ""
    async for event in runner.run_async(user_id="adj", session_id="s", new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


async def adjudicate_async(
    reclass: Reclassification,
    context: EvidenceContext,
    *,
    freshness: str | None = None,
    agent: LlmAgent | None = None,
) -> Adjudication:
    posterior = score_posterior(context.ledger)
    agent = agent or build_adjudicator()
    prompt = _grounding(AdjudicationInput(reclass, context, posterior, freshness))
    raw = await _run_agent(agent, prompt)
    verdict = Verdict.model_validate_json(raw)
    return Adjudication(reclassification=reclass, posterior=posterior, verdict=verdict)


def adjudicate(
    reclass: Reclassification,
    context: EvidenceContext,
    *,
    freshness: str | None = None,
    agent: LlmAgent | None = None,
) -> Adjudication:
    """Synchronous wrapper around the async adjudication."""
    return asyncio.run(adjudicate_async(reclass, context, freshness=freshness, agent=agent))


def grounding_prompt(
    reclass: Reclassification, context: EvidenceContext, *, freshness: str | None = None
) -> str:
    """Expose the grounding prompt for inspection/tests (no LLM call)."""
    return _grounding(AdjudicationInput(reclass, context, score_posterior(context.ledger), freshness))
