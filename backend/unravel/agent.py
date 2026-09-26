"""Shared model identifiers for the Unravel agents.

The five-agent ADK assembly lives in agents.py; this module just holds the Gemini
model ids those agents (and the Adjudicator) reference.

Gemini 3.1 models available in this project (verified 3 Jun 2026, location global):
  gemini-3.1-flash-lite   -> fast Watcher triage
  gemini-3.1-pro-preview  -> Adjudicator (the moat), Planner, Cascade, Steward
"""

MODEL_FLASH = "gemini-3.1-flash-lite"
MODEL_PRO = "gemini-3.1-pro-preview"
