"""Day 1 smoke test: prove the Unravel ADK agent answers end to end via Gemini.

Run:  .venv/bin/python hello.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from unravel.agent import root_agent

load_dotenv(Path(__file__).parent / ".env")

APP = "unravel"
USER = "day1-smoke"
SESSION = "s1"

PROMPT = (
    "An MLH1 variant moved from 'Uncertain significance' to 'Pathogenic' backed by "
    "a 3-star ClinGen expert-panel review. Is this potentially actionable?"
)


async def main() -> None:
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP, session_service=session_service)
    await session_service.create_session(app_name=APP, user_id=USER, session_id=SESSION)

    message = types.Content(role="user", parts=[types.Part(text=PROMPT)])
    print(f"PROMPT: {PROMPT}\n")
    async for event in runner.run_async(
        user_id=USER, session_id=SESSION, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print("AGENT :", event.content.parts[0].text.strip())


if __name__ == "__main__":
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "(unset)")
    print(f"[unravel] Vertex project={project}\n")
    asyncio.run(main())
