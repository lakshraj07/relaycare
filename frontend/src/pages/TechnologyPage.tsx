import { Database, ScanSearch, GitBranch, Users, ShieldCheck, ArrowRight, Boxes, HeartPulse } from 'lucide-react';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

const viewport = { once: true, margin: '-80px' };

const agents = [
  { icon: <Database size={20} color="var(--benign)" />, accent: 'var(--benign)', n: '01', name: 'Scout',
    model: 'Gemini 3.1 Flash-Lite', cls: 'badge-benign',
    desc: 'High-volume delta detection. Reads the curated BigQuery view and the Fivetran feed freshness, and fires only when a watched variant has truly crossed a classification boundary, against the clinic’s historical VUS registry.',
    tools: ['lookup_reclassification', 'check_feed_freshness'] },
  { icon: <ScanSearch size={20} color="var(--path-d)" />, accent: 'var(--path-d)', n: '02', name: 'Arbiter · the moat',
    model: 'Gemini 3.1 Pro', cls: 'badge-path',
    desc: 'Assembles a cited ACMG/AMP evidence ledger, computes a calibrated posterior probability of pathogenicity, and decides triage and action — withholding low-confidence flips. Two variants with the same posterior can warrant opposite actions on review quality.',
    tools: ['assemble_evidence'] },
  { icon: <GitBranch size={20} color="var(--conflict)" />, accent: 'var(--conflict)', n: '03', name: 'Pathfinder',
    model: 'Gemini 3.1 Pro', cls: 'badge-conflict',
    desc: 'For a variant short of the actionable line, ranks every possible next experiment (segregation, tumour MMR/IHC, functional, splicing) by information value, in ACMG currency, and names the single highest-yield move.',
    tools: ['rank_next_experiments'] },
  { icon: <Users size={20} color="var(--primary)" />, accent: 'var(--primary)', n: '04', name: 'Kinship',
    model: 'Gemini 3.1 Pro', cls: 'badge-benign',
    desc: 'On a confirmed actionable upgrade, identifies at-risk relatives from the FHIR pedigree and drafts the clinician alert plus the family fan-out as draft FHIR resources (intent: proposal). Draft-only, never sent.',
    tools: ['find_family'] },
  { icon: <ShieldCheck size={20} color="var(--thread-d)" />, accent: 'var(--thread-d)', n: '05', name: 'Safeguard',
    model: 'Gemini 3.1 Pro', cls: 'badge-vus',
    desc: 'Routes deceased-proband cases to ethics review (never a direct letter), and drafts a ClinVar submission back to the commons when the evidence resolves a variant.',
    tools: ['steward_assessment'] },
];

const pipeline = ['Evidence commons', 'Fivetran MCP', 'BigQuery view', 'Scout', 'Arbiter', 'Pathfinder ‖ Kinship ‖ Safeguard', 'draft FHIR · Firestore'];

const metrics: [string, string, string][] = [
  ['12 / 12', 'the moat, live Gemini 3.1 Pro', '3-star act vs 1-star withhold at the same 0.81 posterior'],
  ['±0.0001', 'calibration to the ClinGen anchors', 'reproduces the published Bayesian probabilities'],
  ['0.20', 'Brier score, computational evidence', 'over 31,432 real Lynch-gene variants'],
  ['0 / 48', 'false alarms on hard negatives', 'ignores cosmetic ClinVar text churn'],
  ['891', 'pytest cases, all green', '74 functions across engine + five agents'],
  ['31,870', 'variants under surveillance', 'curated per-variant BigQuery view'],
];

const cmp: [string, boolean, boolean][] = [
  ['Detect evidence changed', false, true],
  ['Reason over discordant evidence', false, false],
  ['Calibrated posterior + withhold', false, false],
  ['Next-best-experiment planning', false, false],
  ['Fan out to the at-risk family', false, false],
  ['Draft recontact / FHIR write-back', false, false],
];

function Figure({ src, alt, caption }: { src: string; alt: string; caption: ReactNode }) {
  return (
    <motion.figure className="card" style={{ padding: '1rem', margin: 0, background: 'var(--paper)' }}
      initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
      <img src={src} alt={alt} style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 'var(--r-sm)' }} />
      <figcaption className="mono" style={{ fontSize: '.72rem', color: 'var(--faint)', marginTop: '.7rem', textAlign: 'center' }}>{caption}</figcaption>
    </motion.figure>
  );
}

export default function TechnologyPage() {
  return (
    <div className="fade-in">
      {/* HEADER */}
      <section className="sec" style={{ paddingBottom: 'clamp(2rem,1rem+3vw,3rem)' }}>
        <div className="wrapX" style={{ maxWidth: '940px' }}>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }}>
            <div className="mono-tag"><span className="dash" /> Architecture</div>
            <h1 className="display display-fluid" style={{ margin: '1.3rem 0 1.4rem', maxWidth: '15ch' }}>
              Code-first. Auditable. <span className="emph-b">Agentic.</span>
            </h1>
            <p className="body-lg" style={{ maxWidth: '64ch' }}>
              Five real Gemini 3.1 agents in a code-first <strong style={{ color: 'var(--ink)' }}>Google Cloud Agent Builder (ADK)</strong> flow on Cloud Run:
              a <span className="mono" style={{ fontSize: '.86em' }}>SequentialAgent</span> root runs Scout → Arbiter → a
              <span className="mono" style={{ fontSize: '.86em' }}> ParallelAgent</span> fan-out of Pathfinder, Kinship and Safeguard over one shared session.
              Fivetran is the evidence heartbeat (driven through the real MCP server); BigQuery is the curated AI data plane; FHIR R4 in Firestore is the clinical seam.
            </p>
            <div style={{ display: 'flex', gap: '.5rem', marginTop: '1.6rem', flexWrap: 'wrap' }}>
              {['Gemini 3.1 Pro + Flash-Lite', 'Google ADK · Agent Builder', 'Fivetran MCP', 'BigQuery', 'Firestore · FHIR R4', 'Cloud Run', 'Firebase Hosting'].map(t => (
                <span key={t} className="pill"><span className="dot" /> {t}</span>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* SYSTEM ARCHITECTURE */}
      <section className="sec" style={{ paddingTop: 0 }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The system · 01</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 1.4rem', maxWidth: '22ch' }}>One loop, end to end.</h2>
          <p className="body-lg" style={{ maxWidth: '60ch', marginBottom: '1.8rem' }}>
            Public evidence is staged in Google Cloud Storage and synced by Fivetran into a single curated BigQuery view.
            The five-agent system reads that view, drives the Fivetran MCP for freshness, calls Vertex AI Gemini for the
            judgement, pulls AlphaFold structures, and writes draft FHIR to Firestore. A clinician approves; nothing auto-sends.
          </p>
          <Figure src="/diagrams/system-architecture.png" alt="RelayCare system architecture"
            caption="System architecture · data plane (Fivetran → BigQuery) · the agent surface · Google Cloud services · numbered data flows" />
        </div>
      </section>

      {/* THE FIVE AGENTS */}
      <section className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The agents · 02</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 .6rem', maxWidth: '24ch' }}>Five agents, distinct clocks.</h2>
          <p className="body-lg" style={{ maxWidth: '54ch', marginBottom: '2.2rem' }}>
            The agents reason (the brain); deterministic <span className="mono" style={{ fontSize: '.86em' }}>FunctionTool</span>s do the auditable work (the hands). The Arbiter’s verdict fans out to the three specialists in parallel.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: '1.2rem', marginBottom: '2.6rem' }}>
            {agents.map(a => (
              <motion.div key={a.n} className="tile" initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .5 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div className="chip">{a.icon}</div>
                  <span className={`badge ${a.cls}`}>{a.model}</span>
                </div>
                <div className="mono-tag" style={{ color: a.accent, marginTop: '1rem' }}>Agent · {a.n}</div>
                <h3 className="display" style={{ fontSize: '1.35rem', margin: '.4rem 0 .6rem' }}>{a.name}</h3>
                <p style={{ color: 'var(--muted)', marginBottom: '1rem', fontSize: '.92rem' }}>{a.desc}</p>
                <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap', marginTop: 'auto' }}>
                  {a.tools.map(t => (
                    <span key={t} className="mono" style={{ fontSize: '.66rem', color: 'var(--muted)', background: 'var(--paper-2)', border: '1px solid var(--line)', borderRadius: 6, padding: '.22rem .5rem' }}>⚙ {t}</span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          <Figure src="/diagrams/agent-topology.png" alt="RelayCare five-agent ADK topology"
            caption="The ADK flow · SequentialAgent → Scout → Arbiter → ParallelAgent fan-out of Pathfinder / Kinship / Safeguard" />
        </div>
      </section>

      {/* PIPELINE */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The loop · 03</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 2rem', maxWidth: '20ch' }}>Evidence → reasoning → draft.</h2>
          <div className="flow">
            {pipeline.map((p, i) => (
              <div key={p} style={{ display: 'contents' }}>
                <div className="flow-step center" style={{ fontWeight: 600, fontSize: '.86rem' }}>{p}</div>
                {i < pipeline.length - 1 && <div className="flow-arrow hide-sm"><ArrowRight size={16} /></div>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* DATA PLANE / FIVETRAN */}
      <section className="sec">
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The data plane · 04</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 1.4rem', maxWidth: '24ch' }}>Fivetran is the heartbeat, driven from inside the loop.</h2>
          <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.4rem', marginBottom: '1.8rem' }}>
            <div className="tile">
              <div style={{ display: 'flex', gap: '.8rem', alignItems: 'center', marginBottom: '.9rem' }}>
                <Boxes size={22} color="var(--primary)" /><h3 className="display" style={{ fontSize: '1.35rem' }}>The Fivetran MCP seam</h3>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>
                The real <span className="mono" style={{ fontSize: '.86em' }}>fivetran-mcp</span> server is baked into the Cloud Run image and driven live: it checks each feed’s freshness before the Arbiter rules, triggers targeted re-syncs, pauses and resumes connectors, and <strong style={{ color: 'var(--ink)' }}>creates new connectors on demand</strong> to onboard a gene once it is looked up often enough. Full CRUD on live connectors, every write gated by a human approval and logged.
              </p>
              <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap', marginTop: '1rem' }}>
                {['get_connection_state', 'sync_connection', 'modify_connection', 'create_connection'].map(t => (
                  <span key={t} className="mono" style={{ fontSize: '.66rem', color: 'var(--primary-d)', background: 'var(--primary-soft)', borderRadius: 6, padding: '.22rem .5rem' }}>{t}</span>
                ))}
              </div>
            </div>
            <div className="tile">
              <div style={{ display: 'flex', gap: '.8rem', alignItems: 'center', marginBottom: '.9rem' }}>
                <Database size={22} color="var(--thread-d)" /><h3 className="display" style={{ fontSize: '1.35rem' }}>The curated data plane</h3>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>
                Three GCS→BigQuery connectors land ClinVar (assertions + 0–4★ review status), gnomAD v4 allele frequency, and AlphaMissense, unified by a curated per-variant view (<span className="mono" style={{ fontSize: '.85em' }}>sql/variant_evidence.sql</span>) on the GRCh38 coordinate. A custom <strong style={{ color: 'var(--ink)' }}>Fivetran Connector SDK</strong> connector is deployed live too. Any gene not yet onboarded resolves live from the public commons, so the system is disease-agnostic.
              </p>
            </div>
          </div>
          <Figure src="/diagrams/handshake-sequence.png" alt="RelayCare control-plane handshake sequence"
            caption="The control plane · reads are ungated; every warehouse write passes through a human approval and lands in the audit trail" />
        </div>
      </section>

      {/* THE SCIENCE */}
      <section className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The science · 05</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 1.4rem', maxWidth: '24ch' }}>A calibrated probability, not a confidence we invented.</h2>
          <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1.05fr .95fr', gap: '1.6rem', alignItems: 'start' }}>
            <p className="body-lg" style={{ maxWidth: '52ch' }}>
              The posterior is the published, point-based Bayesian formulation of the ACMG/AMP guidelines (Tavtigian 2018/2020).
              Total ACMG points convert to a probability of pathogenicity; the actionable line sits at <strong style={{ color: 'var(--ink)' }}>0.90</strong>.
              AlphaMissense enters as <span className="mono" style={{ fontSize: '.86em' }}>PP3</span> at the ClinGen-recommended calibrated strength (Pejaver 2022),
              never as the classifier, and is <strong style={{ color: 'var(--ink)' }}>down-weighted a tier</strong> for carriers of under-represented ancestries to mitigate known predictor bias.
            </p>
            <div className="card" style={{ padding: '1.3rem 1.4rem', background: 'var(--paper)' }}>
              <div className="mono-tag" style={{ color: 'var(--faint)', marginBottom: '.8rem' }}>backend/unravel/acmg.py</div>
              <pre className="mono" style={{ fontSize: '.74rem', color: 'var(--ink2)', lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap' }}>{`Posterior = (Prior · OddsPath)
          / (1 + Prior · (OddsPath − 1))

Prior     = 0.10
OddsPath  = 350 ^ (points / 8)

anchors:  6 pts → 0.90   (actionable)
         10 pts → 0.994`}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* VALIDATION */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> Validated · 06</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 .6rem', maxWidth: '24ch' }}>Measured on the live model.</h2>
          <p className="body-lg" style={{ maxWidth: '52ch', marginBottom: '2.2rem' }}>
            The headline result is the live Gemini Arbiter’s judgement; the deterministic steps are validated as correctness checks. A research prototype, rigorously evaluated.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '1.1rem' }}>
            {metrics.map(([n, t, s]) => (
              <motion.div key={t} className="card" style={{ padding: '1.5rem' }} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .45 }}>
                <div className="display" style={{ color: 'var(--primary-d)', fontSize: 'clamp(1.9rem,1rem+2.4vw,2.5rem)', lineHeight: 1 }}>{n}</div>
                <div style={{ color: 'var(--ink)', fontWeight: 600, margin: '.7rem 0 .3rem', fontSize: '.96rem' }}>{t}</div>
                <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)' }}>{s}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* SEAMS · FHIR */}
      <section className="sec">
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The clinical seam · 07</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 2.2rem', maxWidth: '24ch' }}>Where the agent meets the EHR.</h2>
          <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.4rem' }}>
            <div className="tile">
              <div style={{ display: 'flex', gap: '.8rem', alignItems: 'center', marginBottom: '.9rem' }}>
                <HeartPulse size={22} color="var(--path)" /><h3 className="display" style={{ fontSize: '1.35rem' }}>FHIR R4, draft-only</h3>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>
                The registry is FHIR R4 (Patient, Observation, FamilyMemberHistory) in Firestore. Every output is a <span className="mono" style={{ fontSize: '.85em' }}>draft</span> resource (<code>intent: proposal, status: draft</code>) a clinician reviews and sends. Aligned to the HL7 Genomics Reporting IG; same webhook pattern, no EHR modification.
              </p>
            </div>
            <div className="tile">
              <div style={{ display: 'flex', gap: '.8rem', alignItems: 'center', marginBottom: '.9rem' }}>
                <ShieldCheck size={22} color="var(--benign)" /><h3 className="display" style={{ fontSize: '1.35rem' }}>Privacy by design</h3>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>
                The cohort is entirely synthetic, so no real patient information is ever handled. The architecture embodies data minimization, full provenance and human-in-the-loop, built to slot into a clinical compliance program. Never patient-facing, never autonomous.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PRIOR ART */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The edge · 08</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 .8rem', maxWidth: '24ch' }}>Prior tools own one link. RelayCare owns the loop.</h2>
          <p className="body-lg" style={{ maxWidth: '48ch', marginBottom: '2rem' }}>
            Monitoring is commoditized; the closed recontact loop, owned by the care team, is not.
          </p>
          <div className="card" style={{ padding: '1.4rem', overflowX: 'auto' }}>
            <table className="cmp">
              <thead>
                <tr>
                  <th>Capability</th>
                  <th>Reanalysis tools <span style={{ color: 'var(--faint)', fontWeight: 400 }}>(alerts)</span></th>
                  <th>Lab amended reports <span style={{ color: 'var(--faint)', fontWeight: 400 }}>(to provider)</span></th>
                  <th className="u">RelayCare</th>
                </tr>
              </thead>
              <tbody>
                {cmp.map(([cap, a, b]) => (
                  <tr key={cap}>
                    <td>{cap}</td>
                    <td className={a ? 'yes' : 'no'}>{a ? '✓' : '✗'}</td>
                    <td className={b ? 'yes' : 'no'}>{b ? '✓' : '✗'}</td>
                    <td className="u yes">✓</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* BUILT WITH */}
      <section className="sec" style={{ paddingTop: 'clamp(3rem,2rem+3vw,4.5rem)' }}>
        <div className="wrapX">
          <div className="card" style={{ padding: '1.5rem 1.8rem', display: 'flex', flexWrap: 'wrap', gap: '.6rem', alignItems: 'center', justifyContent: 'center' }}>
            <span className="mono-tag" style={{ color: 'var(--muted)', marginRight: '.4rem' }}>Built with</span>
            {['Gemini 3.1', 'Google ADK · Agent Builder', 'Vertex AI', 'Cloud Run', 'BigQuery', 'Firestore · FHIR R4', 'Fivetran MCP', 'Firebase Hosting', 'AlphaFold', 'AlphaMissense'].map(t => (
              <span key={t} className="pill"><span className="dot" /> {t}</span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
