"""The five real Gemini agents and the ADK multi-agent assembly.

A genuine multi-agent system (not one prompt in a trench coat): five LlmAgents on
Gemini, orchestrated with the ADK workflow agents the whitepapers prescribe.

    SequentialAgent  unravel_loop
      |
      +-- Watcher (flash-lite)        triage the change, is it worth escalating?
      +-- Adjudicator (pro, the moat) weigh review quality, WITHHOLD weak flips
      +-- ParallelAgent  fan_out      (fan-out / gather, runs concurrently)
            +-- Resolution Planner (pro)   the highest-yield next experiment
            +-- Cascade Coordinator (pro)  draft the family recontact
            +-- Steward (pro)              deceased-proband ethics + give-back

All five share one Session: each agent reads the prior agents' outputs from shared
state (the Adjudicator's verdict fans out to the three specialists) and writes its
own via output_key. The deterministic work lives in tools.py (the hands); these
agents do the judgement (the brain). Draft-only is the human-in-the-loop gate.
"""

from __future__ import annotations

import asyncio
import json
import re

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from . import tools as T
from .agent import MODEL_FLASH, MODEL_PRO

APP = "unravel-loop"


# --- the five agents -----------------------------------------------------------

watcher = LlmAgent(
    name="watcher",
    model=MODEL_FLASH,
    description="Evidence-surveillance triage of a variant reclassification.",
    instruction=(
        "You are the Unravel Watcher. The patient under review is {patient_id}.\n"
        "Call lookup_reclassification with that patient_id, and optionally "
        "check_feed_freshness. Decide whether the detected change is worth "
        "escalating to clinical adjudication and say why in one sentence.\n"
        "Respond with ONLY a JSON object: "
        '{"worth_escalating": true/false, "direction": "...", "summary": "..."}'
    ),
    tools=[FunctionTool(func=T.lookup_reclassification), FunctionTool(func=T.check_feed_freshness)],
    output_key="watch",
)

adjudicator = LlmAgent(
    name="adjudicator",
    model=MODEL_PRO,
    description="The grounded, cited verdict on the reclassification (the moat).",
    instruction=(
        "You are the Unravel Adjudicator, a clinical molecular geneticist. The "
        "patient is {patient_id}. Call assemble_evidence with that patient_id to "
        "get the cited ACMG ledger and the calibrated posterior (treat the "
        "posterior as fact; never invent numbers).\n\n"
        "Reason like a variant scientist and WEIGH REVIEW QUALITY. A 3-4 star "
        "expert-panel classification can justify an actionable verdict even if the "
        "molecular-only posterior is in the uncertain band. A 1-star or "
        "'conflicting classifications' assertion is low confidence: suggestive "
        "molecular evidence alone must NOT drive family recontact, withhold and "
        "recommend the highest-yield next evidence. A move to benign is "
        "reassurance, not an alarm. You never contact a patient; outputs are drafts.\n\n"
        "Respond with ONLY a JSON object: "
        '{"triage": "cold|warm|hot|actionable", "action": "draft_recontact|'
        'withhold_pending_review|recommend_next_evidence|reassure_downgrade", '
        '"withheld": true/false, "posterior": 0.0, "rationale": "2-3 cited sentences"}'
        "\nTriage guide: 'actionable' = act now; 'hot' = suggestive but not yet "
        "sufficient (use this when you WITHHOLD a low-confidence flip); 'warm' = "
        "uncertain, watch; 'cold' = benign / no concern (a downgrade)."
    ),
    tools=[FunctionTool(func=T.assemble_evidence)],
    output_key="verdict",
)

resolution_planner = LlmAgent(
    name="resolution_planner",
    model=MODEL_PRO,
    description="Ranks the next experiment by information value.",
    instruction=(
        "You are the Unravel Resolution Planner for patient {patient_id}. The "
        "Adjudicator's verdict was: {verdict}.\n"
        "Call rank_next_experiments with the patient_id. If the variant is already "
        "actionable, say so and that no resolving experiment is needed. Otherwise "
        "recommend the SINGLE highest-yield next experiment, the one that crosses "
        "the actionable line most cheaply, in ACMG currency, and justify it.\n"
        "Respond with ONLY a JSON object: "
        '{"applicable": true/false, "recommendation": "...", '
        '"top_experiment": "...", "projected_posterior": 0.0}'
    ),
    tools=[FunctionTool(func=T.rank_next_experiments)],
    output_key="plan",
)

cascade_coordinator = LlmAgent(
    name="cascade_coordinator",
    model=MODEL_PRO,
    description="Drafts clinician-gated family recontact for an actionable variant.",
    instruction=(
        "You are the Unravel Cascade Coordinator for patient {patient_id}. The "
        "Adjudicator's verdict was: {verdict}.\n"
        "Only act if the verdict is actionable and NOT withheld. If so, call "
        "find_family and write, for each LIVING carrier and at-risk relative, a "
        "short CLINICIAN-FACING recommendation (third person) for the care team to "
        "review and send, e.g. 'Recommend contacting <name> (<relationship>) to "
        "offer genetic counselling and predictive testing for the reclassified "
        "<variant>.' These are DRAFTS; do NOT write a letter addressed to the "
        "patient ('Dear ...'). If the verdict is not actionable, return "
        "applicable=false.\n"
        "Respond with ONLY a JSON object: "
        '{"applicable": true/false, "drafts": [{"recipient": "...", '
        '"relationship": "...", "recommendation": "..."}]}'
    ),
    tools=[FunctionTool(func=T.find_family)],
    output_key="cascade",
)

steward = LlmAgent(
    name="steward",
    model=MODEL_PRO,
    description="Deceased-proband ethics routing and the ClinVar give-back.",
    instruction=(
        "You are the Unravel Steward for patient {patient_id}. Call "
        "steward_assessment. For any DECEASED carrier, route to an ethics / "
        "next-of-kin consent pathway, never a direct letter to the deceased, and "
        "note their living relatives who may be offered counselling. If the variant "
        "is resolved, draft a one-line ClinVar give-back rationale from the cited "
        "evidence (draft-only; a human submits).\n"
        "Respond with ONLY a JSON object: "
        '{"ethics_routes": [{"deceased": "...", "route": "...", '
        '"living_relatives": [...]}], "give_back": {"classification": "...", '
        '"rationale": "..."}}'
    ),
    tools=[FunctionTool(func=T.steward_assessment)],
    output_key="steward",
)

# --- the assembly: sequential, with a parallel fan-out/gather ------------------

fan_out = ParallelAgent(
    name="fan_out",
    description="Fan out the adjudicated case to three specialists, gather results.",
    sub_agents=[resolution_planner, cascade_coordinator, steward],
)

root_agent = SequentialAgent(
    name="unravel_loop",
    description="Watch -> Adjudicate -> fan out (plan, cascade, steward).",
    sub_agents=[watcher, adjudicator, fan_out],
)


# --- orchestration runner ------------------------------------------------------


def _parse(value) -> dict | str | None:
    """Agent outputs are stored as text; pull the JSON object out if present."""
    if value is None or isinstance(value, dict):
        return value
    text = value if isinstance(value, str) else str(value)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"raw": text.strip()}


def _fhir_drafts(cascade) -> list[dict]:
    """Wrap the Cascade agent's clinician-facing drafts in FHIR Communication
    envelopes (intent: proposal, status: draft), the deterministic safety wrapper
    around the agent-written content. Nothing is sent; a clinician reviews."""
    out: list[dict] = []
    if isinstance(cascade, dict) and cascade.get("applicable"):
        for d in cascade.get("drafts", []):
            out.append({
                "resourceType": "Communication", "status": "draft", "intent": "proposal",
                "category": [{"text": "genetic-result-recontact"}],
                "recipient": [{"display": d.get("recipient")}],
                "payload": [{"contentString": d.get("recommendation") or d.get("message", "")}],
                "note": [{"text": f"At-risk {d.get('relationship', 'relative')}; "
                                  f"clinician review required, not sent."}],
            })
    return out


async def _run_async(patient_id: str) -> dict:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP, user_id="clinic", session_id=patient_id,
        state={"patient_id": patient_id})
    runner = Runner(agent=root_agent, app_name=APP, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(
        text=f"Run the variant-reclassification loop for patient {patient_id}.")])
    async for _ in runner.run_async(user_id="clinic", session_id=patient_id,
                                    new_message=message):
        pass
    session = await session_service.get_session(
        app_name=APP, user_id="clinic", session_id=patient_id)
    st = session.state
    cascade = _parse(st.get("cascade"))
    return {
        "patient_id": patient_id,
        "watch": _parse(st.get("watch")),
        "verdict": _parse(st.get("verdict")),
        "plan": _parse(st.get("plan")),
        "cascade": cascade,
        "fhir_drafts": _fhir_drafts(cascade),
        "steward": _parse(st.get("steward")),
    }


def run_loop(patient_id: str) -> dict:
    """Run the full five-agent ADK loop on one patient and gather every output."""
    return asyncio.run(_run_async(patient_id))


# step metadata for the live stream: agent name -> (UI node, state key)
_STEP = {
    "watcher": ("Watcher", "watch"),
    "adjudicator": ("Adjudicator", "verdict"),
    "resolution_planner": ("Planner", "plan"),
    "cascade_coordinator": ("Cascade", "cascade"),
    "steward": ("Steward", "steward"),
}


async def run_loop_events_async(patient_id: str):
    """Run the loop and yield one event per agent AS IT COMPLETES, so the UI can
    light up each node in real time (Watcher -> Adjudicator -> the parallel
    fan-out) instead of waiting for the whole run."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP, user_id="clinic", session_id=patient_id,
        state={"patient_id": patient_id})
    runner = Runner(agent=root_agent, app_name=APP, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(
        text=f"Run the variant-reclassification loop for patient {patient_id}.")])

    emitted: set[str] = set()
    async for event in runner.run_async(user_id="clinic", session_id=patient_id,
                                        new_message=message):
        author = getattr(event, "author", None)
        if author not in _STEP or author in emitted:
            continue
        if not event.is_final_response() or not (event.content and event.content.parts):
            continue
        text = event.content.parts[0].text
        if not text:
            continue
        emitted.add(author)
        node, key = _STEP[author]
        data = _parse(text)
        payload = {"agent": author, "node": node, "key": key, "data": data}
        if author == "cascade_coordinator":
            payload["fhir_drafts"] = _fhir_drafts(data)
        if author == "adjudicator" and isinstance(data, dict):
            from . import audit
            audit.log("agent", f"{patient_id}: {data.get('triage')} / {data.get('action')}"
                      f"{' (withheld)' if data.get('withheld') else ''}",
                      tone="warn" if data.get("withheld") else "ok")
        yield payload
