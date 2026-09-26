# RelayCare

RelayCare is a prototype for following up when genetic evidence changes after a patient has already received a report.

The public demo is here: [relaycare.vercel.app](https://relaycare.vercel.app)

Built for the AWS × Pear Healthcare Hackathon.

## The reason I built it

My mom has a PhD and works in cancer genetics. I grew up seeing how much care goes into interpreting a genetic result. I also saw how difficult the next part can be. A finding may be updated years later, but the new interpretation still has to reach the patient, the care team, and relatives who may need to know.

RelayCare explores that missing handoff. It watches for a meaningful change, gathers the supporting evidence, identifies the people connected to the case, and prepares a next step for a clinician to review.

The system does not diagnose anyone or contact patients by itself.

## What the demo shows

The demo uses synthetic patient records paired with real public variant histories.

- A variant changes classification in a public evidence source.
- The system checks the supporting evidence and recalculates the ACMG posterior.
- A review step can hold back a weak or conflicting update.
- The patient record is connected to a family pedigree.
- A clinician-facing recontact and cascade-testing draft is prepared.

The dashboard includes a watchlist, evidence view, pedigree, knowledge graph, structural view, approvals, audit trail, and a small assistant for explaining the case data.

## Clinical and privacy boundaries

- The people in the demo are synthetic.
- The variants and public evidence histories are real.
- The output is a draft for clinician review.
- Nothing is sent to a patient automatically.
- This is a research prototype, not a diagnostic device or clinically validated service.

## Architecture

RelayCare is organized as a five-agent graph, not a single assistant prompt. A Google ADK `SequentialAgent` runs Scout and Arbiter in order, then a `ParallelAgent` fans the same case out to Pathfinder, Kinship, and Safeguard. Every agent reads the shared session state and writes a bounded result for the next stage.

| Agent | Responsibility | Tool boundary |
| --- | --- | --- |
| **Scout** | Detects meaningful evidence movement and checks feed freshness. | `lookup_reclassification`, `check_feed_freshness` |
| **Arbiter** | Builds the cited ACMG evidence ledger, weighs review quality, and withholds weak flips. | `assemble_evidence` |
| **Pathfinder** | Ranks the next highest-yield experiment when the evidence is not yet actionable. | `rank_next_experiments` |
| **Kinship** | Finds carriers and at-risk relatives and drafts clinician-facing recontact. | `find_family` |
| **Safeguard** | Routes ethics-sensitive cases and prepares a ClinVar give-back draft. | `steward_assessment` |

The deterministic `FunctionTool` layer performs auditable data work; the Gemini agents make the bounded judgments. Outputs are wrapped as draft FHIR resources with `intent: proposal`, and a clinician reviews before anything is sent. The backend also includes adapters for Fivetran MCP, BigQuery, Firestore, FHIR R4, ClinVar, gnomAD, AlphaMissense, and AlphaFold.

The public dashboard loads its watchlist from `frontend/public/demo-cohort.json`, a small synthetic fixture checked into the site. That keeps the hackathon demo reliable and prevents the public page from depending on a private warehouse or an exposed API route. The FastAPI service remains available for local development and separate deployments, but it is optional for the public walkthrough.

## How the demo moves through the graph

1. Scout spots a possible reclassification in the evidence commons.
2. Arbiter checks the cited evidence and decides whether the change is reliable enough to surface.
3. Pathfinder, Kinship, and Safeguard run concurrently over the Arbiter's verdict.
4. RelayCare returns a reviewable evidence trail, next-step recommendation, family pathway, and ethics/give-back branch.

## Run the frontend locally

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Open \`http://localhost:5173\`.

The public walkthrough loads its synthetic watchlist from \`frontend/public/demo-cohort.json\`; it does not require a public API or a live BigQuery connection.

## Run the backend locally

\`\`\`bash
cd backend
python3.12 -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
# .\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
PYTHONPATH=. uvicorn server:app --reload --port 8000
\`\`\`

Live agent calls require the model, evidence, and database credentials described in the environment example. The frontend landing pages do not need those credentials to run.

## Deploy the frontend

The public frontend is deployed at [relaycare.vercel.app](https://relaycare.vercel.app). The watchlist is served from the checked-in demo fixture, so the public site does not depend on a backend API route.

To create another deployment, use \`frontend\` as the Vercel Root Directory:

- Build command: \`npm run build\`
- Output directory: \`dist\`
The Vercel rewrite in \`frontend/vercel.json\` keeps the React Router pages working when a visitor refreshes a nested route.

## Repository layout

\`\`\`text
backend/
  server.py      FastAPI entry point, agents, evidence logic, and registry
  eval/          calibration and evaluation material
  tests/         backend tests

frontend/
  src/pages/     landing page, mission, technology, and dashboard
  src/dash/      dashboard views and guided tour
  src/api.ts     typed API client
  public/        animations, diagrams, favicon, and brand assets
\`\`\`

## License

Apache-2.0. See [LICENSE](./LICENSE).
