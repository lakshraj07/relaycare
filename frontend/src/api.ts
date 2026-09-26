// Thin client for the RelayCare backend. In dev, Vite proxies /api to the
// FastAPI server on :8000 (see vite.config.ts).

const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const BASE = `${API_ROOT}/api`;

export interface Health {
  status: string;
  service: string;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

// --- legacy time-machine stub (the /app scrubber) ----------------------------

export interface WatchResult {
  year: number;
  stage: string;
  variant: string;
  decision: string;
  review_status: string;
  narration: string;
  source: string;
}

export async function runWatch(year: number): Promise<WatchResult> {
  const res = await fetch(`${BASE}/run-watch?year=${year}`, { method: 'POST' });
  if (!res.ok) throw new Error(`run-watch ${res.status}`);
  return res.json();
}

// --- the real engine ---------------------------------------------------------

export interface BreakdownStep {
  code: string;
  points: number;
  source: string;
  detail: string;
  cumulative_points: number;
  cumulative_posterior: number;
}

export interface PosteriorBreakdown {
  variant: string;
  prior: number;
  prior_posterior: number;
  steps: BreakdownStep[];
  total_points: number;
  odds_path: number;
  posterior: number;
  band: string;
  points_to_actionable: number;
  is_actionable: boolean;
  actionable_line: { points: number; posterior: number };
}

export interface CohortRow {
  patient_id: string;
  patient_name: string;
  deceased: boolean;
  gene: string;
  hgvs_c: string;
  hgvs_p: string | null;
  variant: string;
  recorded_class: string | null;
  recorded_date: string | null;
  current_class: string | null;
  review_stars: number | null;
  direction: string; // escalation | downgrade | lateral | unchanged
  reclassified: boolean;
  points: number;
  posterior: number;
  band: string;
  points_to_actionable: number;
  gnomad_af: number | null;
  am_pathogenicity: number | null;
  am_class: string | null;
  ancestry: string | null;
  ancestry_downweighted: boolean;
  source?: string; // "warehouse" (Fivetran/BigQuery) or "live" (public commons)
  warehouse_sql?: string;
  cited: string[];
  breakdown: PosteriorBreakdown;
}

export interface WarehouseInfo { view: string; sources: string[]; query: string; variant_count?: number | null; }
export async function getWarehouseInfo(): Promise<WarehouseInfo> {
  const res = await fetch(`${BASE}/warehouse`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export interface AuditLogEvent { category: string; text: string; tone?: string; actor?: string; ts_ms?: number; }
export async function getAuditLog(limit = 100): Promise<{ events: AuditLogEvent[] }> {
  const res = await fetch(`${BASE}/audit?limit=${limit}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function approveCase(patient: string, action = 'recontact'): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/approve?patient=${encodeURIComponent(patient)}&action=${encodeURIComponent(action)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// --- data assistant (read-only, grounded explainer) --------------------------

export interface AssistReply {
  answer: string;
  grounded: boolean;
}

export async function assist(question: string, context: string): Promise<AssistReply> {
  const res = await fetch(`${BASE}/assist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, context }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export interface Verdict {
  triage: string;
  action: string;
  withheld: boolean;
  rationale: string;
  key_evidence: string[];
}

export interface Adjudication {
  patient_id: string;
  reclassified: boolean;
  message?: string;
  gene?: string;
  hgvs_c?: string;
  hgvs_p?: string | null;
  current_class?: string;
  review_stars?: number | null;
  posterior?: number;
  points?: number;
  band?: string;
  cited?: string[];
  verdict?: Verdict;
}

export interface StructuralNeighbour {
  residue: number;
  distance: number;
  mean_am: number;
}

export interface HeatmapResidue {
  residue: number;
  mean_am: number;
  plddt: number | null;
}

export interface Structural {
  gene: string;
  uniprot: string;
  residue: number;
  summary: string;
  am_available?: boolean;
  structure_available?: boolean;
  structure_url: string;
  structure_page: string;
  structure_source: string;
  variant_mean_am: number;
  variant_plddt: number | null;
  global_mean_am: number;
  neighbourhood_mean_am: number;
  enrichment: number;
  n_neighbours: number;
  radius_angstrom: number;
  pathogenic_neighbours: StructuralNeighbour[];
  heatmap: HeatmapResidue[];
}

async function detail(res: Response): Promise<string> {
  try {
    const j = await res.json();
    return j.detail || `${res.status}`;
  } catch {
    return `${res.status}`;
  }
}

export async function getCohort(): Promise<CohortRow[]> {
  const res = await fetch(`${BASE}/cohort`);
  if (!res.ok) throw new Error(await detail(res));
  const data = await res.json();
  return data.cohort;
}

// --- the real five-agent ADK loop (Watcher -> Adjudicator -> fan-out) ---------

export interface LoopResult {
  patient_id: string;
  watch: { worth_escalating?: boolean; direction?: string; summary?: string };
  verdict: { triage: string; action: string; withheld: boolean; posterior?: number; rationale: string };
  plan: { applicable?: boolean; recommendation?: string; top_experiment?: string; projected_posterior?: number };
  cascade: { applicable?: boolean; drafts?: { recipient: string; relationship: string; recommendation?: string; message?: string }[] };
  fhir_drafts: Record<string, unknown>[];
  steward: { ethics_routes?: { deceased: string; route?: string; living_relatives?: string[] }[]; give_back?: { classification?: string; rationale?: string } };
}

export async function runLoop(patientId: string): Promise<LoopResult> {
  const res = await fetch(`${BASE}/run-loop?patient=${encodeURIComponent(patientId)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Streaming: the five agents emit one event each as they finish, so the UI can
// light up node by node. Streams direct from Cloud Run (CORS) to avoid CDN
// buffering on the Firebase /api rewrite. In dev, falls back to same-origin.
const STREAM_ORIGIN = API_ROOT;

export interface LoopStreamEvent {
  agent?: string; node?: string; key?: string;
  data?: Record<string, unknown>;
  fhir_drafts?: Record<string, unknown>[];
  error?: string; done?: boolean;
}

export function runLoopStream(
  patientId: string,
  onEvent: (e: LoopStreamEvent) => void,
  onDone: (err?: string) => void,
): () => void {
  const url = `${STREAM_ORIGIN}/api/run-loop-stream?patient=${encodeURIComponent(patientId)}`;
  const es = new EventSource(url);
  es.onmessage = (m) => {
    let e: LoopStreamEvent;
    try { e = JSON.parse(m.data); } catch { return; }
    if (e.done) { es.close(); onDone(e.error); return; }
    if (e.error) { es.close(); onDone(e.error); return; }
    onEvent(e);
  };
  es.onerror = () => { es.close(); onDone('stream error'); };
  return () => es.close();
}

export async function adjudicate(patientId: string): Promise<Adjudication> {
  const res = await fetch(`${BASE}/adjudicate?patient=${encodeURIComponent(patientId)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function getStructural(gene: string, hgvsP: string): Promise<Structural> {
  const res = await fetch(`${BASE}/structural?gene=${gene}&hgvs_p=${encodeURIComponent(hgvsP)}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// --- evidence freshness (Fivetran MCP) ---------------------------------------

export interface Feed {
  schema: string;
  connection_id: string;
  service: string;
  sync_state: string | null;
  succeeded_at: string | null;
  hours_old: number | null;
  is_stale: boolean;
  paused?: boolean | null;
  setup_state?: string | null;
}

export async function getFreshness(): Promise<Feed[]> {
  const res = await fetch(`${BASE}/freshness`);
  if (!res.ok) throw new Error(await detail(res));
  return (await res.json()).feeds;
}

export async function resync(connectionId: string): Promise<{ code?: string; message?: string }> {
  const res = await fetch(`${BASE}/resync?connection_id=${encodeURIComponent(connectionId)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function pauseConnector(connectionId: string, paused: boolean): Promise<{ ok: boolean; paused: boolean }> {
  const res = await fetch(`${BASE}/fivetran/pause?connection_id=${encodeURIComponent(connectionId)}&paused=${paused}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export interface OnboardGeneRow {
  gene: string; count: number; onboarded: boolean;
  connection_id?: string | null; schema?: string | null; n_variants?: number | null; recommended: boolean;
}
export interface OnboardStatus { genes: OnboardGeneRow[]; threshold: number; }

export async function getOnboardStatus(): Promise<OnboardStatus> {
  const res = await fetch(`${BASE}/onboard/status`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function onboardGene(gene: string): Promise<{ ok: boolean; gene: string; connection_id: string; schema: string; n_variants: number }> {
  const res = await fetch(`${BASE}/onboard?gene=${encodeURIComponent(gene)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// --- resolution planner / cascade / steward ----------------------------------

export interface PlanStep {
  label: string;
  code: string;
  strength: string;
  projected_points: number;
  projected_posterior: number;
  projected_band: string;
  crosses_actionable: boolean;
  feasibility: string;
  detail: string;
}

export interface ResolutionPlan {
  variant: string;
  current_points: number;
  current_posterior: number;
  current_band: string;
  gap_to_actionable: number;
  recommendation: string;
  steps: PlanStep[];
}

export interface CascadeDraft {
  for: string;
  patient_id: string;
  relationship: string;
  communication?: Record<string, unknown>;
  risk_assessment?: Record<string, unknown>;
}

export interface CascadeResult {
  variant: string;
  carriers: number;
  relatives: number;
  deceased_carriers: string[];
  drafts: CascadeDraft[];
  note: string;
}

export interface EthicsRoute {
  deceased: string;
  route: string;
  rationale: string;
  living_relatives: string[];
}

export interface StewardResult {
  variant: string;
  has_deceased_carrier: boolean;
  ethics_routes: EthicsRoute[];
  give_back: { variant: string; submitted_classification: string; evidence: string[]; gene: string };
}

export async function getPlan(patientId: string): Promise<ResolutionPlan> {
  const res = await fetch(`${BASE}/plan?patient=${encodeURIComponent(patientId)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function getCascade(patientId: string): Promise<CascadeResult> {
  const res = await fetch(`${BASE}/cascade?patient=${encodeURIComponent(patientId)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function getSteward(patientId: string): Promise<StewardResult> {
  const res = await fetch(`${BASE}/steward?patient=${encodeURIComponent(patientId)}`, { method: 'POST' });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// --- pedigree / graph / add-patient ------------------------------------------

export interface PedigreeMember {
  id: string;
  name: string;
  relationship: string;
  deceased: boolean;
  carrier: boolean;
  recorded_classification: string | null;
  email: string | null;
  phone: string | null;
  recontact_status: string;
}
export interface FamilyHistory { relationship: string | null; deceased: boolean; condition: string | null; }
export interface Pedigree {
  proband_id: string;
  members: PedigreeMember[];
  history: FamilyHistory[];
  needs_contact: PedigreeMember[];
}

export interface GraphNode {
  id: string; label: string; type: string;
  meta?: string; size?: number; detail?: string;
}
export interface GraphEdge {
  source: string; target: string;
  weight?: number; label?: string;
}
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[]; }

export interface NewPatientPayload {
  given: string; family: string; gender?: string; birth?: string;
  email?: string; phone?: string; relative_of?: string; relationship?: string;
  gene?: string; hgvs_c?: string; hgvs_p?: string; gid?: string;
  variant_query?: string; ancestry?: string; recorded_class?: string;
}

export interface ResolvedVariant {
  gid: string; gene: string | null; hgvs_c: string | null;
  hgvs_p: string | null; consequence: string | null;
}

export async function getPedigree(patientId: string): Promise<Pedigree> {
  const res = await fetch(`${BASE}/pedigree?patient=${encodeURIComponent(patientId)}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function getGraph(patientId: string): Promise<Graph> {
  const res = await fetch(`${BASE}/graph?patient=${encodeURIComponent(patientId)}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function addPatient(payload: NewPatientPayload): Promise<{ patient_id: string; ok: boolean; resolved?: ResolvedVariant | null }> {
  const res = await fetch(`${BASE}/patient`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}
