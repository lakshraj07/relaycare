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

## How it works

The repository contains a React and TypeScript frontend, a FastAPI backend, and the evidence and evaluation code behind the workflow.

The agent flow has five responsibilities:

1. Watch for a possible reclassification.
2. Review the evidence and decide whether the change is reliable enough to surface.
3. Suggest the next useful experiment or review step.
4. Find the patient and relatives who may be affected.
5. Route sensitive cases, including deceased-proband cases, to an appropriate human pathway.

The current backend includes adapters for Gemini, Fivetran MCP, BigQuery, Firestore, FHIR R4, ClinVar, gnomAD, AlphaMissense, and AlphaFold. The frontend can be deployed separately from the API.

## Run the frontend locally

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Open \`http://localhost:5173\`.

Vite proxies \`/api\` to \`http://localhost:8000\` during local development.

For a separately hosted API, set:

\`\`\`bash
VITE_API_URL=https://your-api.example.com
\`\`\`

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

The frontend is deployed at [relaycare.vercel.app](https://relaycare.vercel.app).

To create another deployment, use \`frontend\` as the Vercel Root Directory:

- Build command: \`npm run build\`
- Output directory: \`dist\`
- Optional environment variable: \`VITE_API_URL\`

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
