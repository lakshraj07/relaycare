"""Shared model identifiers for the RelayCare agents.

The five-agent ADK assembly lives in agents.py; this module just holds the Gemini
model ids those agents (and the Arbiter) reference.

Gemini 3.1 models available in this project (verified 3 Jun 2026, location global):
  gemini-3.1-flash-lite   -> fast Scout triage
  gemini-3.1-pro-preview  -> Arbiter (the moat), Pathfinder, Kinship, Safeguard
"""

MODEL_FLASH = "gemini-3.1-flash-lite"
MODEL_PRO = "gemini-3.1-pro-preview"
