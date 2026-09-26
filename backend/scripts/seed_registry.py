"""Seed the FHIR R4 demo registry into Firestore and snapshot it locally.

Idempotent: wipes and rewrites the Patient / Observation / FamilyMemberHistory
collections. Writes a local _staging/registry_snapshot.json copy so the agent
tools and tests can run offline against the same data.

Run:  cd backend && .venv/bin/python scripts/seed_registry.py
"""

from __future__ import annotations

import json
from pathlib import Path

from unravel import registry

SNAPSHOT = Path(__file__).resolve().parent.parent / "_staging" / "registry_snapshot.json"


def main() -> None:
    resources = registry.seed()
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(resources, indent=2))

    counts = {k: len(v) for k, v in resources.items()}
    print(f"Seeded Firestore: {counts}")
    print(f"  carriers (Observations): {counts['Observation']}")
    print(f"  patients: {counts['Patient']}")
    print(f"Snapshot -> {SNAPSHOT}")


if __name__ == "__main__":
    main()
