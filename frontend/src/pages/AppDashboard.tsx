import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  Database, Dna, Cpu, Box, Sparkles, Eye, Scale, GitBranch, Users, ShieldCheck,
  List, Network, UserPlus, Server, ScrollText, RefreshCw, ClipboardCheck, Compass,
} from 'lucide-react';
import {
  getCohort, getFreshness, resync, pauseConnector, runLoopStream, getStructural,
  getOnboardStatus, onboardGene, getWarehouseInfo, getAuditLog, approveCase,
  type CohortRow, type Feed, type Adjudication, type ResolutionPlan,
  type KinshipResult, type SafeguardResult, type Structural, type LoopStreamEvent,
  type OnboardStatus, type WarehouseInfo, type AuditLogEvent,
} from '../api';
import PedigreeView from '../dash/PedigreeView';
import GraphView from '../dash/GraphView';
import AddPatientView from '../dash/AddPatientView';
import StructureViewer from '../dash/StructureViewer';
import PosteriorBreakdown from '../dash/PosteriorBreakdown';
import AssistantWidget from '../dash/AssistantWidget';
import Tour, { type TourStep } from '../dash/Tour';

type View = 'watchlist' | 'pedigree' | 'graph' | 'explorer' | 'approvals' | 'audit' | 'add';
const NAV: { id: View; label: string; icon: typeof List }[] = [
  { id: 'watchlist', label: 'Watchlist', icon: List },
  { id: 'pedigree', label: 'Pedigree', icon: Users },
  { id: 'graph', label: 'Knowledge graph', icon: Network },
  { id: 'explorer', label: 'Data explorer', icon: Server },
  { id: 'approvals', label: 'Approvals', icon: ClipboardCheck },
  { id: 'audit', label: 'Audit trail', icon: ScrollText },
  { id: 'add', label: 'Add patient', icon: UserPlus },
];

interface AuditEvent { ts: number; cat: 'fivetran' | 'agent' | 'system'; text: string; tone?: 'ok' | 'warn' | 'info'; }

type NodeState = 'idle' | 'running' | 'done' | 'held';
interface LogLine { agent: string; text: string; tone: 'ok' | 'warn' | 'info'; }

const AGENTS = ['Scout', 'Arbiter', 'Pathfinder', 'Kinship', 'Safeguard'] as const;
type Agent = typeof AGENTS[number];
const AGENT_ICON: Record<Agent, typeof Eye> = {
  Scout: Eye, Arbiter: Scale, Pathfinder: GitBranch, Kinship: Users, Safeguard: ShieldCheck,
};
const SOURCE_ICON: Record<string, typeof Database> = {
  clinvar: Database, gnomad: Dna, alphamissense: Cpu, alphafold: Box, gemini: Sparkles,
};

function bandColor(band: string) {
  const b = (band || '').toLowerCase();
  if (b.includes('pathogenic')) return { fg: 'var(--path-d)', bg: 'var(--path-bg)' };
  if (b.includes('benign')) return { fg: 'var(--benign)', bg: 'var(--benign-bg)' };
  return { fg: 'var(--thread-d)', bg: 'var(--vus-bg)' };
}
function dirChip(dir: string) {
  if (dir === 'escalation') return { label: 'ESCALATION', fg: 'var(--path-d)', bg: 'var(--path-bg)', edge: 'var(--path)' };
  if (dir === 'downgrade') return { label: 'DOWNGRADE', fg: 'var(--benign)', bg: 'var(--benign-bg)', edge: 'var(--benign)' };
  if (dir === 'unchanged') return { label: 'STABLE', fg: 'var(--faint)', bg: 'var(--paper-2)', edge: 'var(--line-2)' };
  return { label: dir.toUpperCase(), fg: 'var(--muted)', bg: 'var(--paper-2)', edge: 'var(--line-2)' };
}
function yearsSince(date: string | null): number | null {
  if (!date) return null;
  const d = new Date(date);
  if (isNaN(d.getTime())) return null;
  return Math.max(0, Math.round((Date.now() - d.getTime()) / (365.25 * 864e5)));
}

const card: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 14,
  padding: '1.1rem 1.2rem', boxShadow: 'var(--sh-sm)',
};
const mono = (s: React.CSSProperties = {}): React.CSSProperties => ({ fontFamily: 'var(--mono)', ...s });
const tag = (fg: string, bg: string): React.CSSProperties => ({
  display: 'inline-block', fontFamily: 'var(--mono)', fontSize: '.68rem', fontWeight: 600,
  padding: '.14rem .5rem', borderRadius: 6, color: fg, background: bg, letterSpacing: '.04em',
});
const eyebrow: React.CSSProperties = {
  fontFamily: 'var(--mono)', fontSize: '.66rem', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--faint)',
};

export default function AppDashboard() {
  const [cohort, setCohort] = useState<CohortRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [feeds, setFeeds] = useState<Feed[] | null>(null);
  const [resyncing, setResyncing] = useState<string | null>(null);
  const [pausing, setPausing] = useState<string | null>(null);
  const [onboardStatus, setOnboardStatus] = useState<OnboardStatus | null>(null);
  const [onboarding, setOnboarding] = useState<string | null>(null);
  const [pendingOnboard, setPendingOnboard] = useState<string | null>(null);
  const [warehouse, setWarehouse] = useState<WarehouseInfo | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEvent[]>([]);
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const [sel, setSel] = useState<CohortRow | null>(null);

  const [nodes, setNodes] = useState<Record<Agent, NodeState>>({
    Scout: 'idle', Arbiter: 'idle', Pathfinder: 'idle', Kinship: 'idle', Safeguard: 'idle',
  });
  const [running, setRunning] = useState(false);
  const [view, setView] = useState<View>('watchlist');
  const [tourOpen, setTourOpen] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);
  const [adj, setAdj] = useState<Adjudication | null>(null);
  const [plan, setPlan] = useState<ResolutionPlan | null>(null);
  const [casc, setCasc] = useState<KinshipResult | null>(null);
  const [stew, setStew] = useState<SafeguardResult | null>(null);
  const [struc, setStruc] = useState<Structural | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const logEvent = (cat: AuditEvent['cat'], text: string, tone?: AuditEvent['tone']) =>
    setEvents((e) => [{ ts: Date.now(), cat, text, tone }, ...e].slice(0, 200));

  useEffect(() => {
    getCohort().then(setCohort).catch((e) => setErr(String(e.message || e)));
    getFreshness().then(setFeeds).catch(() => setFeeds([]));
    getOnboardStatus().then(setOnboardStatus).catch(() => {});
    getWarehouseInfo().then(setWarehouse).catch(() => {});
    getAuditLog().then((r) => setAuditLog(r.events)).catch(() => {});
  }, []);
  useEffect(() => { logRef.current?.scrollTo({ top: 1e6 }); }, [log]);

  const push = (agent: string, text: string, tone: LogLine['tone'] = 'info') =>
    setLog((l) => [...l, { agent, text, tone }]);
  const setNode = (a: Agent, s: NodeState) => setNodes((n) => ({ ...n, [a]: s }));

  function selectPatient(r: CohortRow) {
    setSel(r);
    setNodes({ Scout: 'idle', Arbiter: 'idle', Pathfinder: 'idle', Kinship: 'idle', Safeguard: 'idle' });
    setAdj(null); setPlan(null); setCasc(null); setStew(null); setStruc(null); setLog([]);
    // the evidence dossier (3D structure) is available for ANY patient, not only
    // reclassified ones, so fetch it on select rather than waiting for the loop.
    if (r.hgvs_p) getStructural(r.gene, r.hgvs_p).then(setStruc).catch(() => {});
  }

  async function doResync(f: Feed) {
    setResyncing(f.schema);
    push('Fivetran', `triggering targeted re-sync of ${f.schema} via MCP...`, 'info');
    logEvent('fivetran', `MCP sync_connection → ${f.schema} (${f.connection_id})`, 'info');
    try {
      await resync(f.connection_id);
      push('Fivetran', `${f.schema} re-sync queued`, 'ok');
      logEvent('fivetran', `${f.schema} re-sync queued via Fivetran MCP`, 'ok');
      setFeeds(await getFreshness());
    } catch (e) {
      push('Fivetran', `re-sync failed: ${e}`, 'warn');
      logEvent('fivetran', `${f.schema} re-sync failed: ${e}`, 'warn');
    } finally {
      setResyncing(null);
    }
  }

  async function doPause(f: Feed, paused: boolean) {
    setPausing(f.schema);
    logEvent('fivetran', `MCP modify_connection → ${paused ? 'pause' : 'resume'} ${f.schema}`, 'info');
    try {
      await pauseConnector(f.connection_id, paused);
      logEvent('fivetran', `${f.schema} ${paused ? 'paused' : 'resumed'} via Fivetran MCP`, 'ok');
      setFeeds(await getFreshness());
    } catch (e) {
      logEvent('fivetran', `${f.schema} ${paused ? 'pause' : 'resume'} failed: ${e}`, 'warn');
    } finally {
      setPausing(null);
    }
  }

  function runWatch(target?: CohortRow) {
    const r = target ?? sel;
    if (!r || running) return;
    setRunning(true);
    setAdj(null); setPlan(null); setCasc(null); setStew(null); setLog([]);

    // the live topology: Scout -> Arbiter -> fan-out (Pathfinder ‖ Kinship ‖ Safeguard)
    setNodes({ Scout: 'running', Arbiter: 'idle', Pathfinder: 'idle', Kinship: 'idle', Safeguard: 'idle' });
    push('Scout', `${r.gene} ${r.hgvs_c}: registry "${r.recorded_class}" vs ClinVar "${r.current_class}" (${r.review_stars}★) — five Gemini agents reasoning…`, 'info');
    logEvent('agent', `Watch loop started: ${r.patient_name} (${r.gene} ${r.hgvs_c})`, 'info');
    logEvent('fivetran', 'MCP get_connection_details → checked evidence-feed freshness before adjudication', 'info');

    let verdictActionable = false;
    const fanOutStarted = { v: false };
    const startFanOut = () => {
      if (fanOutStarted.v) return;
      fanOutStarted.v = true;
      setNodes((n) => ({ ...n, Pathfinder: 'running', Kinship: verdictActionable ? 'running' : 'held', Safeguard: 'running' }));
      if (!verdictActionable) push('Kinship', 'held — verdict not actionable, no family recontact drafted', 'warn');
    };

    const onEvent = (e: LoopStreamEvent) => {
      const d = (e.data || {}) as Record<string, any>;
      if (e.agent === 'scout') {
        push('Scout', d.summary || 'change triaged for adjudication', 'ok');
        setNode('Scout', 'done'); setNode('Arbiter', 'running');
      } else if (e.agent === 'arbiter') {
        verdictActionable = d.action === 'draft_recontact' && !d.withheld;
        setAdj({ patient_id: r.patient_id, reclassified: true, verdict: { triage: d.triage, action: d.action, withheld: !!d.withheld, rationale: d.rationale, key_evidence: [] } } as Adjudication);
        push('Arbiter', `verdict: ${d.triage} · ${d.action}${d.withheld ? ' · WITHHELD' : ''}`, d.withheld ? 'warn' : 'ok');
        logEvent('agent', `${r.patient_name} · ${r.gene} ${r.hgvs_c}: ${d.triage} / ${d.action}${d.withheld ? ' (withheld)' : ''}`, d.withheld ? 'warn' : 'ok');
        setNode('Arbiter', 'done');
        startFanOut();
        if (r.hgvs_p) getStructural(r.gene, r.hgvs_p).then(setStruc).catch(() => {});
      } else if (e.agent === 'pathfinder') {
        startFanOut();
        setPlan({ recommendation: d.recommendation || '', steps: [] } as unknown as ResolutionPlan);
        push('Pathfinder', d.recommendation || 'no resolving experiment found', 'ok');
        setNode('Pathfinder', 'done');
      } else if (e.agent === 'kinship') {
        startFanOut();
        if (d.applicable) {
          const drafts = ((d.drafts as any[]) || []).map((x, i) => ({
            for: x.recipient, patient_id: x.recipient, relationship: x.relationship,
            communication: (e.fhir_drafts || [])[i] as Record<string, unknown> | undefined,
            risk_assessment: undefined,
          }));
          const isCarrier = (rel: string) => ['patient', 'proband', 'carrier'].includes((rel || '').toLowerCase());
          const nCarriers = drafts.filter((x) => isCarrier(x.relationship)).length;
          setCasc({ variant: `${r.gene} ${r.hgvs_c}`, carriers: nCarriers, relatives: drafts.length - nCarriers,
            deceased_carriers: [], drafts, note: 'Draft-only (intent: proposal, status: draft). A clinician reviews and sends.' } as KinshipResult);
          push('Kinship', `drafted ${drafts.length} clinician-facing recontact proposal(s)`, 'ok');
          setNode('Kinship', 'done');
        } else {
          setNode('Kinship', 'held');
        }
      } else if (e.agent === 'safeguard') {
        startFanOut();
        const routes = (d.ethics_routes as any[]) || [];
        setStew({ variant: `${r.gene} ${r.hgvs_c}`, has_deceased_carrier: routes.length > 0,
          ethics_routes: routes.map((x: any) => ({ deceased: x.deceased, route: x.route || 'ethics / next-of-kin consent pathway', rationale: '', living_relatives: x.living_relatives || [] })),
          give_back: { variant: `${r.gene} ${r.hgvs_c}`, submitted_classification: (d.give_back as any)?.classification || r.current_class || '', evidence: [], gene: r.gene } } as SafeguardResult);
        if (routes.length > 0) push('Safeguard', 'deceased carrier — routed to ethics / next-of-kin pathway', 'warn');
        else push('Safeguard', 'drafted ClinVar give-back submission', 'ok');
        setNode('Safeguard', 'done');
      }
    };

    const onDone = (err?: string) => {
      if (err && err !== 'stream error') push('Scout', `error: ${err}`, 'warn');
      // any node still 'running' (e.g. a held branch) settles
      setNodes((n) => {
        const out = { ...n };
        (['Pathfinder', 'Kinship', 'Safeguard'] as Agent[]).forEach((a) => {
          if (out[a] === 'running') out[a] = 'done';
        });
        return out;
      });
      setRunning(false);
    };

    runLoopStream(r.patient_id, onEvent, onDone);
  }

  // deep link: /app?patient=<id>&run=1 selects a case and optionally runs the loop
  useEffect(() => {
    if (!cohort) return;
    const params = new URLSearchParams(window.location.search);
    const v = params.get('view');
    if (v && ['watchlist', 'pedigree', 'graph', 'explorer', 'approvals', 'audit', 'add'].includes(v)) setView(v as View);
    const pid = params.get('patient');
    if (!pid) return;
    const row = cohort.find((r) => r.patient_id === pid);
    if (!row) return;
    selectPatient(row);
    if (params.get('run') === '1' && row.reclassified) setTimeout(() => runWatch(row), 400);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cohort]);

  const flagged = cohort?.filter((r) => r.reclassified) ?? [];
  const escalations = flagged.filter((r) => r.direction === 'escalation');
  const maxSilent = Math.max(0, ...(cohort ?? []).map((r) => yearsSince(r.recorded_date) ?? 0));
  const pid = sel?.patient_id ?? cohort?.[0]?.patient_id ?? 'diane-marchetti';
  const refreshCohort = () => {
    getCohort().then(setCohort).catch(() => {});
    getOnboardStatus().then(setOnboardStatus).catch(() => {});
  };

  // human-in-the-loop approval gate before a Fivetran write: open an in-app toast
  const requestOnboard = (gene: string) => setPendingOnboard(gene);

  async function confirmOnboard() {
    const gene = pendingOnboard;
    setPendingOnboard(null);
    if (!gene) return;
    setOnboarding(gene);
    logEvent('fivetran', `approved: onboard ${gene} → staging evidence + MCP create_connection`, 'info');
    try {
      const r = await onboardGene(gene);
      logEvent('fivetran', `MCP create_connection → ${r.schema} (${r.connection_id}), ${r.n_variants} variants, syncing`, 'ok');
      getOnboardStatus().then(setOnboardStatus).catch(() => {});
      getFreshness().then(setFeeds).catch(() => {});
    } catch (e) {
      logEvent('fivetran', `onboard ${gene} failed: ${e}`, 'warn');
    } finally {
      setOnboarding(null);
    }
  }

  async function doApprove(r: CohortRow) {
    setApproved((a) => ({ ...a, [r.patient_id]: true }));
    logEvent('agent', `clinician approved recontact for ${r.patient_name}`, 'ok');
    try {
      await approveCase(r.patient_id, 'recontact');
      getAuditLog().then((x) => setAuditLog(x.events)).catch(() => {});
    } catch { /* keep optimistic UI */ }
  }

  // the tour selects a real case so the workup/structure views are populated
  // without needing the (slow) full loop to run.
  const ensureCase = () => {
    if (!cohort) return;
    if (sel?.patient_id === 'diane-marchetti') return;
    const d = cohort.find((r) => r.patient_id === 'diane-marchetti') ?? cohort[0];
    if (d) selectPatient(d);
  };

  const tourSteps: TourStep[] = [
    { title: 'Welcome to RelayCare', body: 'A quick tour of how RelayCare watches for genetic variants that change meaning over time, and closes the loop back to the patient. Use Next, or skip anytime.' },
    { selector: '[data-tour="tabs"]', title: 'Seven views', body: 'Everything lives behind these tabs. The tour will move through them for you, but you can explore freely afterwards.', onEnter: () => setView('watchlist') },
    { selector: '[data-tour="metrics"]', title: 'The scale', body: 'Tens of thousands of variants kept under surveillance, and how many have already reclassified in this clinic’s cohort.', onEnter: () => { setView('watchlist'); ensureCase(); } },
    { selector: '[data-tour="watchlist"]', title: 'The watchlist', body: 'Each row is a patient with a past variant of uncertain significance (VUS), ranked by urgency and by how many years it has gone unreviewed.', onEnter: () => setView('watchlist') },
    { selector: '[data-tour="posterior"]', title: 'A calibrated probability', body: 'This is the published point-based Bayesian ACMG probability of pathogenicity, not an invented score. About 0.90 is the line where a variant becomes actionable.', onEnter: () => { setView('watchlist'); ensureCase(); } },
    { selector: '[data-tour="pipeline"]', title: 'Five Gemini agents', body: 'The Scout detects the change, the Arbiter judges it and withholds on weak evidence, then the Pathfinder, Kinship and Safeguard agents fan out in parallel.', onEnter: () => { setView('watchlist'); ensureCase(); } },
    { selector: '[data-tour="structure"]', title: 'The structural story', body: 'The real AlphaFold 3D model, coloured by AlphaMissense. Red residues are predicted more damaging. It is supporting evidence, never the verdict on its own.', onEnter: () => { setView('watchlist'); ensureCase(); } },
    { selector: '[data-tour="connectors"]', title: 'Fivetran keeps it fresh', body: 'The public evidence commons, synced into BigQuery. Check connector health and run re-syncs, pauses and resumes, all through the real Fivetran MCP server.', onEnter: () => setView('explorer') },
    { selector: '[data-tour="onboarding"]', title: 'Onboard a gene on demand', body: 'A gene looked up often enough is promoted into the warehouse: the agent creates a real Fivetran connector via the MCP, behind a human approval.', onEnter: () => setView('explorer') },
    { selector: '[data-tour="graph"]', title: 'The evidence network', body: 'Every node around one variant: ClinVar, gnomAD, AlphaMissense, AlphaFold, the calibrated posterior, and the family. Click any node to see why it matters.', onEnter: () => setView('graph') },
    { selector: '[data-tour="approvals"]', title: 'Human-in-the-loop', body: 'Nothing reaches a patient automatically. A clinician approves every family recontact here before anything is sent.', onEnter: () => setView('approvals') },
    { selector: '[data-tour="audit"]', title: 'A full audit trail', body: 'Every verdict, every Fivetran action and every approval is recorded and persisted, so the whole loop stays accountable after the fact.', onEnter: () => setView('audit') },
    { selector: '[data-tour="assistant"]', title: 'Ask the data', body: 'Anytime, open this assistant to ask how the data flows, what a number means, or how to add a patient. It explains what is on your screen, and never diagnoses.', onEnter: () => setView('watchlist') },
  ];

  return (
    <main style={{ maxWidth: 1320, margin: '0 auto', padding: '1.4rem 1.6rem 4rem', overflowX: 'clip' }}>
      <style>{`
        @keyframes uvpulse { 0%,100% { opacity:1 } 50% { opacity:.4 } }
        @keyframes uvspin { to { transform: rotate(360deg) } }
        @keyframes uvfade { from { opacity:0; transform: translateY(4px) } to { opacity:1; transform:none } }
        .uv-row { transition: box-shadow .15s ease, background .15s ease; }
        .uv-row:hover { background: var(--paper-2) !important; box-shadow: var(--sh-sm); }
        .uv-log > div { animation: uvfade .25s ease both; }
        .uv-workgrid > * { min-width: 0; }
        .uv-workgrid > * > * { min-width: 0; max-width: 100%; }
        @media (max-width: 1024px) { .uv-workgrid { grid-template-columns: 1fr !important; } }
      `}</style>

      {/* header + source rail */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={eyebrow}>Variant commons watch</div>
          <h1 style={{ fontSize: '1.7rem', margin: '.15rem 0' }}>Variant reclassification surveillance</h1>
          <div style={{ fontSize: '.82rem', color: 'var(--muted)' }}>
            Any gene, any variant: onboarded genes are served from the Fivetran warehouse, anything else live from the public commons. Verdicts from Gemini 3.1 Pro, structure from AlphaFold. Synthetic cohort.
          </div>
          <button onClick={() => setTourOpen(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '.4rem', marginTop: '.6rem',
              border: '1px solid var(--primary)', background: 'var(--primary-soft)', color: 'var(--primary)',
              borderRadius: 999, padding: '.4rem .85rem', fontSize: '.8rem', fontWeight: 700, cursor: 'pointer' }}>
            <Compass size={14} /> Take a tour
          </button>
        </div>
        <div style={{ ...card, padding: '.7rem .8rem', minWidth: 330 }}>
          <div style={{ ...eyebrow, marginBottom: '.45rem' }}>Evidence sources</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.4rem' }}>
            {(feeds ?? []).map((f) => (
              <SourceChip key={f.schema} label={f.schema} fresh={!f.is_stale}
                sub={f.hours_old != null ? `${f.hours_old}h` : '?'}
                busy={resyncing === f.schema} onClick={() => doResync(f)} />
            ))}
            {!feeds && <span style={{ ...mono({ fontSize: '.7rem' }), color: 'var(--faint)' }}>checking Fivetran via MCP...</span>}
            <SourceChip label="alphafold" fresh sub="db" />
            <SourceChip label="gemini" fresh sub="3.1pro" />
          </div>
          <div style={{ ...mono({ fontSize: '.62rem' }), color: 'var(--faint)', marginTop: '.45rem' }}>
            click a Fivetran source to trigger a targeted re-sync
          </div>
        </div>
      </div>

      <TabBar view={view} setView={setView} />

      <div style={{ marginTop: '1.1rem' }}>
        <div style={{ minWidth: 0, display: 'grid', gap: '1rem' }}>
          {err && <div style={{ ...card, ...tag('var(--path-d)', 'var(--path-bg)'), whiteSpace: 'normal' }}>Backend error: {err}. Is the API running on :8000?</div>}

          {view === 'pedigree' && cohort && <PedigreeView patientId={pid} cohort={cohort} />}
          {view === 'graph' && <div data-tour="graph"><GraphView patientId={pid} cohort={cohort} onPick={selectPatient} /></div>}
          {view === 'explorer' && <ExplorerView feeds={feeds} events={events} resyncing={resyncing} pausing={pausing} onResync={doResync} onPause={doPause} onboard={onboardStatus} onboarding={onboarding} onOnboard={requestOnboard} warehouse={warehouse} />}
          {view === 'audit' && <div data-tour="audit"><AuditView cohort={cohort} events={events} persisted={auditLog} /></div>}
          {view === 'approvals' && <div data-tour="approvals"><ApprovalsView cohort={cohort} approved={approved} onReview={(r) => { selectPatient(r); setView('watchlist'); }} onApprove={doApprove} /></div>}
          {view === 'add' && cohort && <AddPatientView cohort={cohort} onAdded={refreshCohort} />}

          {view === 'watchlist' && (<>
          {/* impact strip */}
          <div data-tour="metrics" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '.8rem' }}>
            <Metric n={warehouse?.variant_count ? warehouse.variant_count.toLocaleString() : '…'} label="variants under surveillance" />
            <Metric n={cohort ? `${flagged.length}` : '…'} label="reclassified in cohort" />
            <Metric n={`${escalations.length}`} label="escalations to act on" tone="path" />
            <Metric n={`${maxSilent}`} label="years silent (max)" tone="path" />
            <Metric n={feeds ? `${feeds.filter((f) => !f.is_stale && !f.paused).length}/${feeds.length}` : '…'} label="Fivetran feeds fresh" tone="benign" />
          </div>

          <div className="uv-workgrid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,340px) minmax(0,1fr)', gap: '1.1rem', alignItems: 'start' }}>
        {/* worklist */}
        <div data-tour="watchlist" style={{ ...card, padding: '.9rem', minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={eyebrow}>Watchlist · ranked by urgency</div>
            <span style={{ ...mono({ fontSize: '.66rem' }), color: 'var(--faint)' }}>{cohort?.length ?? 0} cases</span>
          </div>
          <div style={{ display: 'grid', gap: '.4rem', marginTop: '.6rem' }}>
            {!cohort && <div style={{ color: 'var(--faint)', fontSize: '.85rem' }}>loading cohort from BigQuery...</div>}
            {cohort?.map((r) => {
              const bc = bandColor(r.band); const dc = dirChip(r.direction);
              const isSel = sel?.patient_id === r.patient_id;
              const silent = yearsSince(r.recorded_date);
              return (
                <div key={r.patient_id} className="uv-row" onClick={() => selectPatient(r)}
                  style={{
                    cursor: 'pointer', borderRadius: 10, padding: '.55rem .6rem',
                    border: '1px solid var(--line)',
                    background: 'var(--surface)',
                    boxShadow: isSel ? 'inset 0 0 0 1.5px var(--ink)' : 'none',
                  }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '.4rem', alignItems: 'baseline' }}>
                    <span style={{ fontWeight: 700, fontSize: '.88rem' }}>{r.patient_name}{r.deceased ? ' †' : ''}</span>
                    <span style={tag(dc.fg, dc.bg)}>{dc.label}</span>
                  </div>
                  <div style={{ ...mono({ fontSize: '.7rem' }), color: 'var(--muted)', marginTop: '.15rem', display: 'flex', alignItems: 'center', gap: '.4rem', flexWrap: 'wrap' }}>
                    <span>{r.gene} {r.hgvs_c} · {r.review_stars}★</span>
                    {r.source === 'live' && (
                      <span style={tag('var(--thread)', 'var(--primary-soft)')} title="Resolved live from the public commons (gene not yet onboarded to the Fivetran warehouse)">live</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginTop: '.35rem' }}>
                    <Gauge p={r.posterior} />
                    <span style={mono({ fontSize: '.72rem', color: bc.fg, fontWeight: 600 })}>{r.posterior.toFixed(2)}</span>
                  </div>
                  {silent != null && r.reclassified && (
                    <div style={{ ...mono({ fontSize: '.64rem' }), color: silent >= 3 ? 'var(--path-d)' : 'var(--faint)', marginTop: '.2rem' }}>
                      silent {silent} yr{silent === 1 ? '' : 's'}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* case workup */}
        <div style={{ display: 'grid', gap: '1rem', minWidth: 0 }}>
          {!sel && <div style={{ ...card, color: 'var(--faint)' }}>Select a case from the watchlist to open the workup and run the agent loop.</div>}

          {sel && (
            <>
              <div style={card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '.6rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.25rem' }}>{sel.patient_name}{sel.deceased ? ' †' : ''}</h2>
                    <div style={mono({ fontSize: '.76rem', color: 'var(--muted)', marginTop: '.15rem' })}>
                      {sel.gene} {sel.hgvs_c}{sel.hgvs_p ? ` (${sel.hgvs_p})` : ''}
                    </div>
                    <div style={{ fontSize: '.8rem', color: 'var(--muted)', marginTop: '.3rem' }}>
                      registry: <b>{sel.recorded_class}</b> → ClinVar now: <b style={{ color: bandColor(sel.current_class || '').fg }}>{sel.current_class}</b> ({sel.review_stars}★)
                    </div>
                    <div style={{ fontSize: '.74rem', color: sel.reclassified ? 'var(--path-d)' : 'var(--muted)', marginTop: '.3rem', display: 'flex', alignItems: 'center', gap: '.35rem' }}>
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: sel.reclassified ? 'var(--path)' : 'var(--benign)', animation: 'uvpulse 2.2s ease-in-out infinite' }} />
                      {sel.reclassified
                        ? `Reclassified since the registry record — ${sel.direction} flagged for review.`
                        : 'Under active surveillance — no change since the registry record. Re-runs re-check the live evidence.'}
                    </div>
                  </div>
                  <button onClick={() => runWatch()} disabled={running}
                    style={{
                      background: 'var(--thread)', color: '#fff', fontWeight: 700,
                      borderRadius: 9, padding: '.6rem 1.1rem', fontSize: '.85rem', opacity: running ? .7 : 1,
                      cursor: running ? 'default' : 'pointer',
                    }}>
                    {running ? 'Running loop…' : sel.reclassified ? '▶ Run watch loop' : '▶ Run surveillance check'}
                  </button>
                </div>

                <div data-tour="pipeline" style={{ display: 'flex', alignItems: 'center', gap: '.25rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                  {AGENTS.map((a, i) => (
                    <div key={a} style={{ display: 'flex', alignItems: 'center' }}>
                      <PipelineNode name={a} state={nodes[a]} />
                      {i < AGENTS.length - 1 && <span style={{ color: 'var(--line-2)', margin: '0 .05rem' }}>→</span>}
                    </div>
                  ))}
                </div>
              </div>

              {/* posterior + ledger */}
              <div data-tour="posterior" style={card}>
                <div style={eyebrow}>Calibrated posterior · point-based ACMG</div>
                <div style={{ display: 'flex', gap: '1.4rem', alignItems: 'center', marginTop: '.6rem', flexWrap: 'wrap' }}>
                  <BigGauge p={sel.posterior} />
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <div style={{ display: 'flex', gap: '.5rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: 'var(--serif)', fontSize: '2.2rem', color: bandColor(sel.band).fg }}>{sel.posterior.toFixed(2)}</span>
                      <span style={tag(bandColor(sel.band).fg, bandColor(sel.band).bg)}>{sel.band}</span>
                      <span style={mono({ fontSize: '.72rem', color: 'var(--faint)' })}>{sel.points} pts · gap {sel.points_to_actionable}</span>
                    </div>
                    <div style={{ marginTop: '.5rem' }}>
                      {sel.cited.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no molecular criteria met</div>}
                      {sel.cited.map((c, i) => (
                        <div key={i} style={mono({ fontSize: '.74rem', color: 'var(--muted)', padding: '.08rem 0' })}>{c}</div>
                      ))}
                    </div>
                  </div>
                </div>
                {sel.breakdown && (
                  <div style={{ marginTop: '1rem', paddingTop: '.9rem', borderTop: '1px solid var(--line)' }}>
                    <PosteriorBreakdown breakdown={sel.breakdown} />
                  </div>
                )}
                {sel.warehouse_sql && (
                  <details style={{ marginTop: '.9rem' }}>
                    <summary style={{ ...mono({ fontSize: '.66rem', color: 'var(--faint)' }), cursor: 'pointer' }}>
                      BigQuery query the agents ran · {sel.source === 'live' ? 'served live from source APIs' : 'Fivetran-synced warehouse'}
                    </summary>
                    <pre style={{ ...mono({ fontSize: '.64rem' }), color: 'var(--muted)', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 8, padding: '.6rem .7rem', marginTop: '.4rem', overflowX: 'auto', whiteSpace: 'pre', lineHeight: 1.5 }}>{sel.warehouse_sql}</pre>
                  </details>
                )}
              </div>

              {adj?.verdict && (
                <OutCard title="Arbiter verdict · Gemini 3.1 Pro" edge={adj.verdict.withheld ? 'var(--path)' : 'var(--thread)'}>
                  <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap', marginBottom: '.5rem' }}>
                    <span style={tag(adj.verdict.triage === 'actionable' ? 'var(--path-d)' : 'var(--thread-d)', adj.verdict.triage === 'actionable' ? 'var(--path-bg)' : 'var(--vus-bg)')}>triage: {adj.verdict.triage}</span>
                    <span style={tag('var(--ink)', 'var(--paper-2)')}>action: {adj.verdict.action}</span>
                    <span style={tag(adj.verdict.withheld ? 'var(--path-d)' : 'var(--benign)', adj.verdict.withheld ? 'var(--path-bg)' : 'var(--benign-bg)')}>{adj.verdict.withheld ? 'withheld' : 'not withheld'}</span>
                  </div>
                  <p style={{ fontSize: '.88rem', lineHeight: 1.55 }}>{adj.verdict.rationale}</p>
                </OutCard>
              )}

              {plan && (
                <OutCard title="Pathfinder · next best evidence" edge="var(--conflict)">
                  <p style={{ fontSize: '.88rem', marginBottom: '.5rem' }}>{plan.recommendation}</p>
                  {plan.steps.slice(0, 4).map((s) => (
                    <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '.5rem', fontSize: '.76rem', padding: '.2rem 0', borderTop: '1px solid var(--line)' }}>
                      <span style={{ flex: 1 }}>{s.label} <span style={mono({ color: 'var(--faint)' })}>({s.code} {s.strength})</span></span>
                      <span style={mono({ color: s.crosses_actionable ? 'var(--path-d)' : 'var(--muted)' })}>→ {s.projected_posterior.toFixed(2)}</span>
                      {s.crosses_actionable && <span style={tag('var(--path-d)', 'var(--path-bg)')}>crosses</span>}
                    </div>
                  ))}
                </OutCard>
              )}

              {casc && <CascadeCard casc={casc} />}

              {stew && (stew.has_deceased_carrier || stew.give_back) && (
                <OutCard title="Safeguard · ethics + give-back" edge="var(--benign)">
                  {stew.ethics_routes.map((e) => (
                    <div key={e.deceased} style={{ fontSize: '.85rem', marginBottom: '.4rem' }}>
                      <b>{e.deceased}</b> (deceased) → {e.route}. Living relatives: {e.living_relatives.join(', ') || 'none on file'}.
                    </div>
                  ))}
                  <div style={{ fontSize: '.82rem', color: 'var(--muted)' }}>
                    Draft ClinVar give-back: {stew.give_back.variant} → <b>{stew.give_back.submitted_classification}</b> (draft-only)
                  </div>
                </OutCard>
              )}

              {struc && (
                <div data-tour="structure">
                <OutCard title="Structural story · AlphaFold + AlphaMissense" edge="var(--thread-d)">
                  <p style={{ fontSize: '.86rem', marginBottom: '.5rem' }}>{struc.summary}</p>
                  {struc.structure_available === false ? (
                    <div style={{ ...tag('var(--muted)', 'var(--paper-2)'), whiteSpace: 'normal', fontSize: '.78rem', padding: '.6rem .7rem', borderRadius: 8 }}>
                      AlphaFold has no single 3D model for {struc.gene} (the protein exceeds the prediction-length limit). The verdict still rests on population, in-silico and ClinVar evidence.
                    </div>
                  ) : (
                    <>
                      <StructureViewer structural={struc} />
                      <div style={{ display: 'flex', gap: '1.4rem', flexWrap: 'wrap', marginTop: '.7rem' }}>
                        {struc.am_available !== false && <Stat n={`${struc.enrichment}x`} label="enrichment" tone="path" />}
                        {struc.am_available !== false && <Stat n={struc.variant_mean_am.toFixed(2)} label="residue AM" />}
                        <Stat n={struc.variant_plddt != null ? `${struc.variant_plddt}` : 'n/a'} label="pLDDT" />
                        <Stat n={`${struc.n_neighbours}`} label={`neighbours (${struc.radius_angstrom}A)`} />
                      </div>
                      {struc.am_available === false && (
                        <div style={{ fontSize: '.72rem', color: 'var(--faint)', marginTop: '.5rem' }}>
                          Per-residue AlphaMissense enrichment is computed for onboarded genes; this gene is served live, so the structure is shown without the enrichment overlay.
                        </div>
                      )}
                      <a href={struc.structure_page} target="_blank" rel="noreferrer" style={{ fontSize: '.82rem', fontWeight: 600, display: 'inline-block', marginTop: '.5rem' }}>
                        View on AlphaFold DB ({struc.uniprot}) &rarr;
                      </a>
                    </>
                  )}
                </OutCard>
                </div>
              )}

              {/* activity log */}
              <div style={{ ...card, background: '#11141f', border: '1px solid #20263a' }}>
                <div style={{ ...eyebrow, color: '#7f8aa3' }}>Agent activity log</div>
                <div ref={logRef} className="uv-log" style={{ maxHeight: 200, overflowY: 'auto', marginTop: '.5rem' }}>
                  {log.length === 0 && <div style={mono({ fontSize: '.76rem', color: '#5b647a' })}>idle — run the watch loop</div>}
                  {log.map((l, i) => (
                    <div key={i} style={mono({ fontSize: '.74rem', padding: '.12rem 0', color: l.tone === 'warn' ? '#e8b06a' : l.tone === 'ok' ? '#7fd1a3' : '#aeb6c8' })}>
                      <span style={{ color: '#5b647a' }}>[{l.agent}]</span> {l.text}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
          </>)}
        </div>
      </div>

      {pendingOnboard && (
        <div style={{ position: 'fixed', left: 22, bottom: 22, zIndex: 1000, width: 360, maxWidth: 'calc(100vw - 44px)',
          ...card, padding: '1rem 1.1rem', boxShadow: 'var(--sh-lg)', animation: 'uvfade .2s ease both' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
            <ShieldCheck size={16} color="var(--primary)" />
            <span style={{ ...eyebrow, color: 'var(--primary)' }}>Approval required</span>
          </div>
          <div style={{ fontSize: '.86rem', color: 'var(--ink)', marginTop: '.5rem', lineHeight: 1.5 }}>
            Onboard <b>{pendingOnboard}</b> to the warehouse? The agent will stage its evidence to GCS and <b>create a real Fivetran connector via the MCP</b>, then sync it into BigQuery.
          </div>
          <div style={{ display: 'flex', gap: '.5rem', marginTop: '.85rem', justifyContent: 'flex-end' }}>
            <button onClick={() => setPendingOnboard(null)}
              style={{ border: '1px solid var(--line-2)', background: 'var(--surface)', color: 'var(--muted)', borderRadius: 8, padding: '.45rem .9rem', fontSize: '.8rem', fontWeight: 600, cursor: 'pointer' }}>Dismiss</button>
            <button onClick={confirmOnboard}
              style={{ border: 'none', background: 'var(--primary)', color: '#fff', borderRadius: 8, padding: '.45rem 1rem', fontSize: '.8rem', fontWeight: 700, cursor: 'pointer', boxShadow: '0 2px 8px rgba(36,80,164,.25)' }}>Approve &amp; onboard</button>
          </div>
        </div>
      )}

      <AssistantWidget view={view} context={[
        `view=${view}`,
        cohort ? `cohort: ${cohort.length} patients, ${flagged.length} reclassified, ${escalations.length} escalation(s), max ${maxSilent} years silent` : 'cohort: loading',
        warehouse?.variant_count ? `warehouse: ${warehouse.variant_count} variants under surveillance` : '',
        feeds ? `Fivetran feeds: ${feeds.map((f) => `${f.schema}=${f.paused ? 'paused' : f.is_stale ? 'stale' : 'fresh'}`).join(', ')}` : '',
        sel ? `selected case: ${sel.patient_name}, ${sel.gene} ${sel.hgvs_c}${sel.hgvs_p ? ` (${sel.hgvs_p})` : ''}, posterior ${sel.posterior.toFixed(2)} (${sel.band}), ${sel.review_stars}-star, registry "${sel.recorded_class}" vs ClinVar "${sel.current_class}", direction ${sel.direction}, ${sel.reclassified ? 'reclassified' : 'stable'}${sel.source === 'live' ? ', served live from the commons' : ''}` : 'no case selected',
        struc && sel ? `structure on screen: ${sel.gene} AlphaFold ${struc.uniprot ?? ''}${struc.am_available !== false && typeof struc.variant_mean_am === 'number' ? `, residue AlphaMissense ${struc.variant_mean_am.toFixed(2)}, enrichment ${struc.enrichment}x` : ''}` : '',
        onboardStatus?.genes?.length ? `onboarding candidates: ${onboardStatus.genes.map((g) => `${g.gene}${g.onboarded ? '(in warehouse)' : `(${g.count} live lookups)`}`).join(', ')}` : '',
      ].filter(Boolean).join('\n')} />

      <Tour steps={tourSteps} open={tourOpen} onClose={() => setTourOpen(false)} />
    </main>
  );
}

function TabBar({ view, setView }: { view: View; setView: (v: View) => void }) {
  return (
    <div data-tour="tabs" style={{ ...card, padding: '.35rem', marginTop: '1.1rem', display: 'flex', gap: '.2rem', flexWrap: 'wrap', position: 'sticky', top: 8, zIndex: 20 }}>
      {NAV.map((n) => {
        const on = view === n.id;
        const Icon = n.icon;
        return (
          <button key={n.id} onClick={() => setView(n.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '.45rem', padding: '.5rem .85rem', borderRadius: 9,
              background: on ? 'var(--primary)' : 'transparent', color: on ? '#fff' : 'var(--muted)',
              fontWeight: on ? 700 : 600, fontSize: '.82rem', cursor: 'pointer',
              boxShadow: on ? '0 2px 8px rgba(36,80,164,.22)' : 'none', transition: 'background .15s, color .15s',
            }}>
            <Icon size={15} /> {n.label}
          </button>
        );
      })}
    </div>
  );
}

function ViewIntro({ icon: Icon, title, body }: { icon: typeof Server; title: string; body: string }) {
  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.65rem' }}>
        <span style={{ width: 34, height: 34, borderRadius: 9, background: 'var(--primary-soft)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
          <Icon size={17} color="var(--primary)" />
        </span>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>{title}</div>
          <div style={{ fontSize: '.8rem', color: 'var(--muted)', marginTop: '.1rem' }}>{body}</div>
        </div>
      </div>
    </div>
  );
}

function ExplorerView({ feeds, events, resyncing, pausing, onResync, onPause, onboard, onboarding, onOnboard, warehouse }: {
  feeds: Feed[] | null; events: AuditEvent[]; resyncing: string | null; pausing: string | null;
  onResync: (f: Feed) => void; onPause: (f: Feed, paused: boolean) => void;
  onboard: OnboardStatus | null; onboarding: string | null; onOnboard: (gene: string) => void;
  warehouse: WarehouseInfo | null;
}) {
  const fivetranEvents = events.filter((e) => e.cat === 'fivetran');
  const fresh = (feeds ?? []).filter((f) => !f.is_stale && !f.paused).length;
  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <ViewIntro icon={Server} title="Data explorer · Fivetran + BigQuery"
        body="The evidence commons, kept fresh in BigQuery by Fivetran. Check connector health and run targeted re-syncs, pauses and resumes through the Fivetran MCP server (CRUD on live connectors)." />

      {warehouse && (
        <div style={card}>
          <div style={eyebrow}>Curated AI data plane · BigQuery view</div>
          <div style={{ fontSize: '.76rem', color: 'var(--muted)', marginTop: '.3rem' }}>
            Fivetran lands the raw sources in BigQuery; a curated view models them into the single table the five agents query. The agents reason over the data plane, not raw feeds.
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', flexWrap: 'wrap', marginTop: '.7rem' }}>
            {warehouse.sources.map((s) => (
              <span key={s} style={mono({ fontSize: '.66rem', color: 'var(--muted)', background: 'var(--paper-2)', padding: '.2rem .5rem', borderRadius: 6 })}>{s.split('.').slice(1).join('.')}</span>
            ))}
            <span style={{ color: 'var(--faint)' }}>→</span>
            <span style={mono({ fontSize: '.68rem', color: 'var(--primary)', background: 'var(--primary-soft)', padding: '.2rem .5rem', borderRadius: 6, fontWeight: 600 })}>{warehouse.view.split('.').slice(1).join('.')}</span>
          </div>
          <pre style={{ ...mono({ fontSize: '.66rem' }), color: 'var(--ink)', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 8, padding: '.7rem .8rem', marginTop: '.7rem', overflowX: 'auto', whiteSpace: 'pre', lineHeight: 1.5 }}>{warehouse.query}</pre>
        </div>
      )}

      <div data-tour="connectors" style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '.4rem' }}>
          <div style={eyebrow}>Evidence connectors · BigQuery destination</div>
          {feeds && <div style={mono({ fontSize: '.66rem', color: 'var(--faint)' })}>health check · {fresh}/{feeds.length} connectors healthy</div>}
        </div>
        <div style={{ display: 'grid', gap: '.5rem', marginTop: '.7rem' }}>
          {(feeds ?? []).map((f) => {
            const busy = resyncing === f.schema || pausing === f.schema;
            const dotCol = f.paused ? 'var(--faint)' : f.is_stale ? 'var(--path)' : 'var(--benign)';
            return (
              <div key={f.schema} style={{ display: 'flex', alignItems: 'center', gap: '.7rem', padding: '.6rem .7rem', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--paper)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotCol, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '.86rem' }}>{f.schema}</span>
                    {f.paused && <span style={tag('var(--faint)', 'var(--paper-2)')}>paused</span>}
                    {f.service && <span style={mono({ fontSize: '.6rem', color: 'var(--faint)' })}>{f.service}</span>}
                  </div>
                  <div style={mono({ fontSize: '.64rem', color: 'var(--faint)' })}>{f.connection_id} · {f.setup_state ?? f.sync_state ?? 'synced'} · {f.hours_old != null ? `${f.hours_old}h ago` : 'unknown'}</div>
                </div>
                <button onClick={() => onPause(f, !f.paused)} disabled={busy}
                  style={{ border: '1px solid var(--line-2)', background: 'var(--surface)', borderRadius: 8, padding: '.4rem .65rem', fontSize: '.72rem', fontWeight: 600, color: 'var(--muted)', cursor: busy ? 'default' : 'pointer', flexShrink: 0 }}>
                  {pausing === f.schema ? '…' : f.paused ? 'Resume' : 'Pause'}
                </button>
                <button onClick={() => onResync(f)} disabled={busy}
                  style={{ display: 'flex', alignItems: 'center', gap: '.35rem', border: '1px solid var(--line-2)', background: 'var(--surface)', borderRadius: 8, padding: '.4rem .7rem', fontSize: '.72rem', fontWeight: 600, color: 'var(--primary)', cursor: busy ? 'default' : 'pointer', flexShrink: 0 }}>
                  <RefreshCw size={12} style={{ animation: resyncing === f.schema ? 'uvspin 1s linear infinite' : 'none' }} /> {resyncing === f.schema ? 'syncing…' : 'Re-sync'}
                </button>
              </div>
            );
          })}
          {!feeds && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>checking Fivetran via MCP…</div>}
          {feeds && feeds.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no Fivetran feeds reachable</div>}
        </div>
      </div>

      <div data-tour="onboarding" style={card}>
        <div style={eyebrow}>Gene onboarding · demand-driven</div>
        <div style={{ fontSize: '.76rem', color: 'var(--muted)', marginTop: '.3rem' }}>
          Genes resolved live often enough are promoted into the warehouse: the agent stages the evidence and creates a real Fivetran connector via the MCP, then syncs it into BigQuery.
        </div>
        <div style={{ display: 'grid', gap: '.5rem', marginTop: '.7rem' }}>
          {(onboard?.genes ?? []).map((g) => (
            <div key={g.gene} style={{ display: 'flex', alignItems: 'center', gap: '.7rem', padding: '.55rem .7rem', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--paper)' }}>
              <Dna size={14} color={g.onboarded ? 'var(--benign)' : 'var(--primary)'} style={{ flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, fontSize: '.86rem' }}>{g.gene}</span>
                  {g.onboarded && <span style={tag('var(--benign)', 'var(--benign-bg)')}>warehouse</span>}
                  {!g.onboarded && g.recommended && <span style={tag('var(--primary)', 'var(--primary-soft)')}>recommended</span>}
                </div>
                <div style={mono({ fontSize: '.64rem', color: 'var(--faint)' })}>
                  {g.onboarded
                    ? `onboarded · ${g.schema ?? ''} · ${g.n_variants ?? '?'} variants · ${g.connection_id ?? ''}`
                    : `${g.count} live lookup${g.count === 1 ? '' : 's'}${g.recommended ? ` · ≥ ${onboard?.threshold} → ready to onboard` : ''}`}
                </div>
              </div>
              {!g.onboarded && (
                <button onClick={() => onOnboard(g.gene)} disabled={!!onboarding}
                  style={{ border: 'none', background: g.recommended ? 'var(--primary)' : 'var(--surface)', color: g.recommended ? '#fff' : 'var(--primary)', borderRadius: 8, padding: '.4rem .75rem', fontSize: '.72rem', fontWeight: 700, cursor: onboarding ? 'default' : 'pointer', flexShrink: 0, boxShadow: g.recommended ? 'none' : 'inset 0 0 0 1px var(--line-2)' }}>
                  {onboarding === g.gene ? 'onboarding…' : 'Onboard to warehouse'}
                </button>
              )}
            </div>
          ))}
          {(!onboard || onboard.genes.length === 0) && (
            <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no live-resolved genes yet · add a patient with a non-MMR variant to see onboarding candidates</div>
          )}
        </div>
      </div>

      <div style={card}>
        <div style={eyebrow}>Fivetran MCP action log</div>
        <div style={{ marginTop: '.5rem', maxHeight: 280, overflowY: 'auto' }}>
          {fivetranEvents.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no MCP actions yet · trigger a re-sync, or run a watch loop (it checks freshness first)</div>}
          {fivetranEvents.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: '.6rem', padding: '.3rem 0', borderTop: i ? '1px solid var(--line)' : 'none' }}>
              <span style={mono({ fontSize: '.63rem', color: 'var(--faint)', flexShrink: 0 })}>{new Date(e.ts).toLocaleTimeString()}</span>
              <span style={mono({ fontSize: '.72rem', color: e.tone === 'warn' ? 'var(--path-d)' : e.tone === 'ok' ? 'var(--benign)' : 'var(--muted)' })}>{e.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AuditView({ cohort, events, persisted }: { cohort: CohortRow[] | null; events: AuditEvent[]; persisted: AuditLogEvent[] }) {
  const reclass = (cohort ?? []).filter((r) => r.reclassified);
  const catChip = (cat: string) =>
    cat === 'fivetran' ? tag('var(--primary)', 'var(--primary-soft)')
      : cat === 'agent' ? tag('var(--thread-d)', 'var(--vus-bg)')
        : cat === 'approval' ? tag('var(--benign)', 'var(--benign-bg)')
          : tag('var(--muted)', 'var(--paper-2)');
  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <ViewIntro icon={ScrollText} title="Audit trail"
        body="Every reclassification, agent verdict, Fivetran action and clinician approval is recorded (persisted in Firestore, surviving across sessions). Draft-only by design: nothing reaches a patient without human approval." />

      <div style={card}>
        <div style={eyebrow}>Reclassification ledger · {reclass.length} flagged</div>
        <div style={{ marginTop: '.6rem', display: 'grid', gap: '.1rem' }}>
          {reclass.map((r) => {
            const dc = dirChip(r.direction);
            return (
              <div key={r.patient_id} style={{ display: 'flex', alignItems: 'center', gap: '.6rem', padding: '.45rem .1rem', borderTop: '1px solid var(--line)' }}>
                <span style={{ ...tag(dc.fg, dc.bg), flexShrink: 0 }}>{dc.label}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 600, fontSize: '.84rem' }}>{r.patient_name}</span>
                  <span style={mono({ fontSize: '.71rem', color: 'var(--muted)', marginLeft: '.5rem' })}>{r.gene} {r.hgvs_c}</span>
                </div>
                <span style={mono({ fontSize: '.69rem', color: 'var(--muted)' })}>{r.recorded_class} → {r.current_class}</span>
              </div>
            );
          })}
          {reclass.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no reclassifications flagged</div>}
        </div>
      </div>

      <div style={card}>
        <div style={eyebrow}>Recorded history · persisted ({persisted.length})</div>
        <div style={{ marginTop: '.5rem', maxHeight: 360, overflowY: 'auto' }}>
          {persisted.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no recorded events yet · run a watch loop, a Fivetran action, or an approval</div>}
          {persisted.map((e, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '.55rem', padding: '.34rem 0', borderTop: i ? '1px solid var(--line)' : 'none' }}>
              <span style={mono({ fontSize: '.61rem', color: 'var(--faint)', flexShrink: 0 })}>{e.ts_ms ? new Date(e.ts_ms).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</span>
              <span style={{ ...catChip(e.category), flexShrink: 0 }}>{e.category}</span>
              <span style={mono({ fontSize: '.72rem', color: e.tone === 'warn' ? 'var(--path-d)' : e.tone === 'ok' ? 'var(--benign)' : 'var(--muted)' })}>{e.text}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={card}>
        <div style={eyebrow}>This session</div>
        <div style={{ marginTop: '.5rem', maxHeight: 220, overflowY: 'auto' }}>
          {events.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no actions this session yet</div>}
          {events.map((e, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '.55rem', padding: '.3rem 0', borderTop: i ? '1px solid var(--line)' : 'none' }}>
              <span style={mono({ fontSize: '.61rem', color: 'var(--faint)', flexShrink: 0 })}>{new Date(e.ts).toLocaleTimeString()}</span>
              <span style={{ ...catChip(e.cat), flexShrink: 0 }}>{e.cat}</span>
              <span style={mono({ fontSize: '.72rem', color: e.tone === 'warn' ? 'var(--path-d)' : e.tone === 'ok' ? 'var(--benign)' : 'var(--muted)' })}>{e.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ApprovalsView({ cohort, approved, onReview, onApprove }: {
  cohort: CohortRow[] | null; approved: Record<string, boolean>;
  onReview: (r: CohortRow) => void; onApprove: (r: CohortRow) => void;
}) {
  const queue = (cohort ?? []).filter((r) => r.reclassified).sort((a, b) => Number(b.direction === 'escalation') - Number(a.direction === 'escalation'));
  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <ViewIntro icon={ClipboardCheck} title="Approval queue · human in the loop"
        body="Flagged cases awaiting a clinician. The agents draft; a human reviews and approves. Nothing reaches a patient autonomously." />
      <div style={card}>
        <div style={eyebrow}>Awaiting review · {queue.filter((r) => !approved[r.patient_id]).length} open</div>
        <div style={{ display: 'grid', gap: '.5rem', marginTop: '.7rem' }}>
          {queue.map((r) => {
            const dc = dirChip(r.direction);
            const done = approved[r.patient_id];
            return (
              <div key={r.patient_id} style={{ display: 'flex', alignItems: 'center', gap: '.7rem', padding: '.6rem .7rem', border: '1px solid var(--line)', borderRadius: 10, background: done ? 'var(--benign-bg)' : 'var(--paper)' }}>
                <span style={{ ...tag(dc.fg, dc.bg), flexShrink: 0 }}>{dc.label}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 700, fontSize: '.86rem' }}>{r.patient_name}</span>
                  <span style={mono({ fontSize: '.7rem', color: 'var(--muted)', marginLeft: '.5rem' })}>{r.gene} {r.hgvs_c} · post {r.posterior.toFixed(2)}</span>
                </div>
                <button onClick={() => onReview(r)} style={{ border: '1px solid var(--line-2)', background: 'var(--surface)', color: 'var(--muted)', borderRadius: 8, padding: '.4rem .75rem', fontSize: '.74rem', fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}>Review case</button>
                {done
                  ? <span style={{ ...tag('var(--benign)', 'var(--benign-bg)'), flexShrink: 0 }}>approved</span>
                  : <button onClick={() => onApprove(r)} style={{ border: 'none', background: 'var(--primary)', color: '#fff', borderRadius: 8, padding: '.4rem .8rem', fontSize: '.74rem', fontWeight: 700, cursor: 'pointer', flexShrink: 0 }}>Approve recontact</button>}
              </div>
            );
          })}
          {queue.length === 0 && <div style={mono({ fontSize: '.74rem', color: 'var(--faint)' })}>no cases awaiting approval</div>}
        </div>
      </div>
    </div>
  );
}

function SourceChip({ label, fresh, sub, busy, onClick }: { label: string; fresh: boolean; sub: string; busy?: boolean; onClick?: () => void }) {
  const Icon = SOURCE_ICON[label] ?? Database;
  return (
    <button onClick={onClick} disabled={!onClick || busy}
      style={{ display: 'flex', alignItems: 'center', gap: '.35rem', border: '1px solid var(--line)', background: 'var(--paper)', borderRadius: 999, padding: '.25rem .55rem', cursor: onClick ? 'pointer' : 'default' }}>
      <Icon size={13} color="var(--muted)" style={{ animation: busy ? 'uvspin 1s linear infinite' : 'none' }} />
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: fresh ? 'var(--benign)' : 'var(--path)', animation: fresh && !busy ? 'uvpulse 2.2s ease-in-out infinite' : 'none' }} />
      <span style={mono({ fontSize: '.68rem', fontWeight: 600, color: 'var(--ink)' })}>{label}</span>
      <span style={mono({ fontSize: '.62rem', color: 'var(--faint)' })}>{busy ? 'syncing' : sub}</span>
    </button>
  );
}

function Metric({ n, label, tone, sub }: { n: string; label: string; tone?: 'path' | 'benign'; sub?: string }) {
  const col = tone === 'path' ? 'var(--path-d)' : tone === 'benign' ? 'var(--benign)' : 'var(--ink)';
  return (
    <div style={{ ...card, padding: '1rem 1.1rem' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: '.6rem', fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--faint)' }}>{label}</div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: '2.1rem', color: col, lineHeight: 1, marginTop: '.5rem' }}>{n}</div>
      {sub && <div style={{ fontSize: '.68rem', color: 'var(--muted)', marginTop: '.3rem' }}>{sub}</div>}
    </div>
  );
}

function Stat({ n, label, tone }: { n: string; label: string; tone?: 'path' }) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: '1.4rem', color: tone === 'path' ? 'var(--path-d)' : 'var(--ink)' }}>{n}</div>
      <div style={mono({ fontSize: '.64rem', color: 'var(--faint)' })}>{label}</div>
    </div>
  );
}

function Gauge({ p }: { p: number }) {
  return (
    <span style={{ position: 'relative', flex: 1, height: 7, borderRadius: 999, background: 'linear-gradient(90deg,var(--benign),#d7c98f 40%,#e7b06a 56%,var(--path))' }}>
      <span style={{ position: 'absolute', top: -2, left: '90%', width: 1.5, height: 11, background: 'rgba(23,26,43,.3)' }} />
      <span style={{ position: 'absolute', top: -2.5, left: `calc(${p * 100}% - 1px)`, width: 2.5, height: 12, background: 'var(--ink)', borderRadius: 2, transition: 'left .8s cubic-bezier(.2,.8,.2,1)' }} />
    </span>
  );
}

function BigGauge({ p }: { p: number }) {
  const [w, setW] = useState(0);
  useEffect(() => { const t = setTimeout(() => setW(p), 60); return () => clearTimeout(t); }, [p]);
  return (
    <div style={{ width: 150 }}>
      <div style={{ position: 'relative', height: 14, borderRadius: 999, background: 'linear-gradient(90deg,var(--benign),#d7c98f 40%,#e7b06a 56%,var(--path))' }}>
        <div style={{ position: 'absolute', top: -4, left: '90%', width: 2, height: 22, background: 'rgba(23,26,43,.35)' }} />
        <div style={{ position: 'absolute', top: -5, left: `calc(${w * 100}% - 1.5px)`, width: 3, height: 24, background: 'var(--ink)', borderRadius: 2, transition: 'left 1s cubic-bezier(.2,.8,.2,1)' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '.3rem' }}>
        <span style={mono({ fontSize: '.6rem', color: 'var(--faint)' })}>benign</span>
        <span style={mono({ fontSize: '.6rem', color: 'var(--faint)' })}>0.90</span>
        <span style={mono({ fontSize: '.6rem', color: 'var(--faint)' })}>path</span>
      </div>
    </div>
  );
}

function PipelineNode({ name, state }: { name: Agent; state: NodeState }) {
  const Icon = AGENT_ICON[name];
  const map = {
    idle: { bg: 'var(--paper-2)', fg: 'var(--faint)' },
    running: { bg: 'var(--vus-bg)', fg: 'var(--thread-d)' },
    done: { bg: 'var(--benign-bg)', fg: 'var(--benign)' },
    held: { bg: '#fdf1d9', fg: '#8a6300' },
  }[state];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '.3rem', background: map.bg, border: '1px solid var(--line)', borderRadius: 8, padding: '.32rem .5rem' }}>
      <Icon size={13} color={map.fg} style={{ animation: state === 'running' ? 'uvpulse 1s ease-in-out infinite' : 'none' }} />
      <span style={mono({ fontSize: '.68rem', fontWeight: 600, color: map.fg })}>
        {name}{state === 'done' ? ' ✓' : state === 'held' ? ' ⏸' : state === 'running' ? '…' : ''}
      </span>
    </div>
  );
}

function CascadeCard({ casc }: { casc: KinshipResult }) {
  const [showFhir, setShowFhir] = useState(false);
  const [fhirIdx, setFhirIdx] = useState(0);
  const draft = casc.drafts[fhirIdx];
  const fhirBundle = draft ? [draft.communication, draft.risk_assessment].filter(Boolean) : [];

  return (
    <OutCard title="Kinship · draft recontact" edge="var(--path)">
      <div style={{ fontSize: '.88rem', marginBottom: '.4rem' }}>
        <b>{casc.drafts.length}</b> draft FHIR proposals, {casc.carriers} carrier(s) + {casc.relatives} at-risk relative(s)
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.35rem' }}>
        {casc.drafts.map((d, i) => (
          <button key={d.patient_id} onClick={() => { setFhirIdx(i); setShowFhir(true); }}
            style={{
              ...tag('var(--thread-d)', 'var(--vus-bg)'),
              cursor: 'pointer', border: fhirIdx === i && showFhir ? '1.5px solid var(--thread-d)' : '1px solid transparent',
            }}>
            {d.for}, {d.relationship}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', marginTop: '.5rem' }}>
        <button onClick={() => setShowFhir(!showFhir)}
          style={{
            fontFamily: 'var(--mono)', fontSize: '.72rem', fontWeight: 600,
            padding: '.3rem .6rem', borderRadius: 6,
            border: '1px solid var(--line)', cursor: 'pointer',
            background: showFhir ? 'var(--vus-bg)' : 'var(--surface)',
            color: showFhir ? 'var(--thread-d)' : 'var(--muted)',
          }}>
          {showFhir ? 'Hide FHIR' : 'View as FHIR'}
        </button>
        <span style={{ fontFamily: 'var(--mono)', fontSize: '.64rem', color: 'var(--faint)' }}>{casc.note}</span>
      </div>
      {showFhir && fhirBundle.length > 0 && (
        <pre style={{
          marginTop: '.5rem', padding: '.7rem', borderRadius: 8,
          background: '#0d1117', border: '1px solid #20263a', color: '#aeb6c8',
          fontFamily: 'var(--mono)', fontSize: '.7rem', lineHeight: 1.5,
          maxHeight: 300, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {JSON.stringify({ resourceType: 'Bundle', type: 'collection', entry: fhirBundle.map((r) => ({ resource: r })) }, null, 2)}
        </pre>
      )}
    </OutCard>
  );
}

function OutCard({ title, edge, children }: { title: string; edge: string; children: ReactNode }) {
  return (
    <div style={{ ...card, animation: 'uvfade .3s ease both' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: edge, flex: '0 0 auto' }} />
        <div style={eyebrow}>{title}</div>
      </div>
      <div style={{ marginTop: '.5rem' }}>{children}</div>
    </div>
  );
}
