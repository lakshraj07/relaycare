import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, RefreshCw, ScanSearch, Users } from 'lucide-react';
import Funnel from '../components/Funnel';

const viewport = { once: true, margin: '-80px' };

export default function LandingPage() {
  return (
    <div className="fade-in">
      {/* ===== HERO ===== */}
      <section style={{ position: 'relative', minHeight: '92dvh', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', overflow: 'hidden' }}>
        <svg aria-hidden width="620" height="620" viewBox="0 0 200 200" style={{ position: 'absolute', top: '-4%', right: '-6%', opacity: .07, color: 'var(--primary)' }}>
          <path d="M60 10 C140 50, 60 110, 140 150 M60 50 C140 90, 60 150, 140 190" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" />
          {[20, 55, 90, 125, 160].map((y) => <line key={y} x1="68" y1={y} x2="132" y2={y + 18} stroke="currentColor" strokeWidth="3" strokeLinecap="round" />)}
        </svg>

        <div className="wrapX" style={{ paddingTop: '8rem', paddingBottom: 'clamp(3rem,2rem+5vw,6rem)' }}>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }}>
            <div className="mono-tag"><span className="dash" /> RelayCare · clinical-genomics agent</div>
            <h1 className="display display-fluid" style={{ margin: '1.4rem 0 1.6rem', maxWidth: '17ch' }}>
              The result said <span className="emph-b">uncertain</span>. The evidence said <span className="emph">otherwise</span>. Nobody told the family.
            </h1>
            <p className="body-lg" style={{ maxWidth: '56ch' }}>
              RelayCare is a five-agent system that re-reads the world’s evolving variant evidence. The moment a Variant of
              Uncertain Significance is reclassified as pathogenic, it drafts the recontact for the patient and every
              at-risk relative, for a clinician to review and send.
            </p>
            <div style={{ display: 'flex', gap: '.9rem', marginTop: '2.2rem', flexWrap: 'wrap' }}>
              <Link to="/app" className="btn btn-primary">Run the simulator <ArrowRight size={18} /></Link>
              <Link to="/mission" className="btn btn-ghost">Read the mission</Link>
            </div>
          </motion.div>
        </div>

        <div className="wrapX" style={{ paddingBottom: '1.6rem' }}>
          <div className="mono-tag" style={{ color: 'var(--faint)' }}><span className="dash" style={{ background: 'var(--line-2)' }} /> scroll to follow the thread</div>
        </div>
      </section>

      {/* ===== THESIS · 01 ===== */}
      <section id="thesis" className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX thesis-grid">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> The thesis · 01</div>
            <h2 className="display display-mid" style={{ margin: '1.2rem 0 1.6rem' }}>
              A genetic result isn’t a fact. It’s a <span className="emph-b">timestamp</span>.
            </h2>
            <div className="body-lg" style={{ maxWidth: '58ch', display: 'grid', gap: '1.1rem' }}>
              <p>
                A “Variant of Uncertain Significance” means the lab can’t yet call it benign or dangerous, so clinically
                nothing is done. The patient is told: <em>“if it ever changes, we’ll let you know.”</em>
              </p>
              <p>
                But the evidence doesn’t stand still. Over 18 to 24 months, often 5+ years, a real fraction of these
                variants get reclassified. The dangerous ones flip to pathogenic. And no system is watching on the
                patient’s behalf. The promise is quietly broken.
              </p>
            </div>
          </motion.div>

          <motion.aside initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .7 }}>
            <blockquote className="pullquote">
              “The duty to recontact is, in ACMG’s own words, <span className="emph">desirable but not currently feasible.</span>”
            </blockquote>
            <ol className="stack">
              <li><span className="k">01 · evidence</span><span className="v">The databases move. ClinVar, gnomAD and AlphaMissense update continuously, but a filed report never re-reads them.</span></li>
              <li><span className="k">02 · patient</span><span className="v">By the time a variant flips, the proband may be in remission or gone. The result lands in an inbox with no owner.</span></li>
              <li><span className="k">03 · family</span><span className="v">A germline variant is heritable. The life now at risk is a relative’s, and cascade testing is never offered.</span></li>
            </ol>
          </motion.aside>
        </div>
      </section>

      {/* ===== BY THE NUMBERS ===== */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> By the numbers</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 2.2rem', maxWidth: '22ch' }}>The gap is measured, and it is wide.</h2>
          <div className="grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '1.4rem' }}>
            <StatCard num="8.7%" accent="var(--path-d)" t="of reclassified VUS are upgraded to pathogenic, a median 1.86 years after the original report." src="Mersch et al., JAMA 2018 · 1.45M individuals" />
            <StatCard num="<30%" accent="var(--primary-d)" t="of eligible first-degree relatives ever undergo cascade testing for a known family variant." src="npj Genomic Medicine, 2024" />
            <StatCard num="≤41%" accent="var(--primary-d)" t="of patients have their clinical management changed once a variant is reclassified." src="Makhnoon et al., Cancer Medicine 2023" />
          </div>
        </div>
      </section>

      {/* ===== THE LOOP · 02 (horizontal funnel) ===== */}
      <Funnel />

      {/* ===== CAPABILITIES · 03 ===== */}
      <section id="capabilities" className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> What it does · 03</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 .6rem', maxWidth: '22ch' }}>
            Five agents. One loop. Genuinely multi-agent.
          </h2>
          <p className="body-lg" style={{ maxWidth: '52ch', marginBottom: '2.8rem' }}>
            Five Gemini 3.1 agents share one session: Scout detects, Arbiter judges and withholds, and a parallel fan-out moves the case through Pathfinder, Kinship and Safeguard. They reason; auditable tools execute.
          </p>

          <motion.div className="tiles-3" initial="h" whileInView="s" viewport={viewport}
            variants={{ h: {}, s: { transition: { staggerChildren: .12 } } }}>
            <Tile kicker="Scout · Flash-Lite" accent="var(--primary)" icon={<RefreshCw size={22} color="var(--primary)" />}
              title="Scout" body="Continuous Fivetran sync across the evidence commons, driven through the real MCP server. Reads freshness, triggers re-syncs, and runs an auditable delta against the historical VUS registry."
              sketch={<SketchSync />} />
            <Tile kicker="Arbiter · Pro · the moat" accent="var(--conflict)" icon={<ScanSearch size={22} color="var(--conflict)" />}
              title="Arbiter" body="Assembles a cited ACMG ledger, computes a calibrated posterior, and withholds low-confidence flips. Two identical scores, opposite actions, decided on review quality, the part a rules engine gets wrong."
              sketch={<SketchAdjudicate />} />
            <Tile kicker="Pathfinder ‖ Kinship ‖ Safeguard" accent="var(--path)" icon={<Users size={22} color="var(--path)" />}
              title="The fan-out" body="Three agents in parallel: Pathfinder ranks the next-best experiment, Kinship drafts the family recontact as FHIR, and Safeguard routes ethics and a ClinVar give-back. Draft-only, clinician reviewed."
              sketch={<SketchFanout />} />
          </motion.div>
        </div>
      </section>

      {/* ===== THE REFRAME · 04 ===== */}
      <section id="reframe" className="sec reframe-grid-wrap" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX reframe-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: 'clamp(2rem,1rem+4vw,4.5rem)', alignItems: 'center' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> The reframe · 04</div>
            <div className="stat-huge" style={{ marginTop: '1.2rem' }}>1 in 3</div>
            <p className="body-lg" style={{ marginTop: '1rem', maxWidth: '34ch' }}>
              at-risk relatives are <span className="emph">never even told</span> they may carry the family’s variant.
            </p>
            <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginTop: '.9rem' }}>Ahsan et al., PEC Innovation 2023 · meta-analysis, 11,711 relatives</div>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .65 }}>
            <h2 className="display display-mid" style={{ marginBottom: '1.2rem' }}>
              The delay isn’t a flaw. It’s the <span className="emph-b">reason</span>.
            </h2>
            <p className="body-lg" style={{ maxWidth: '54ch' }}>
              When a germline variant flips, it’s a family emergency, and the beneficiary is the living relative, not only
              the proband. RelayCare is <strong style={{ color: 'var(--ink)' }}>cascade-first</strong>, and disease-agnostic:
              the same loop fails across hereditary cancer and rare paediatric disease alike.
            </p>
            <div style={{ display: 'flex', gap: '.6rem', marginTop: '1.6rem', flexWrap: 'wrap' }}>
              <span className="pill"><span className="dot" /> 18 to 24 months to reclassify</span>
              <span className="pill"><span className="dot" /> family-scale impact</span>
              <span className="pill"><span className="dot" /> cancer + rare disease</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ===== THE OPPORTUNITY · 05 (money / market) ===== */}
      <section className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> The opportunity · 05</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 .6rem', maxWidth: '24ch' }}>
            A fast-growing market, measured in lives and in dollars.
          </h2>
          <p className="body-lg" style={{ maxWidth: '54ch', marginBottom: '2.6rem' }}>
            Genetic testing is scaling fast, and every test is a living data asset that keeps changing. RelayCare turns that
            churn into recurring, actionable signal, exactly the kind of evolving-data problem a modern pipeline is built for.
          </p>
          <div className="reframe-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'clamp(2rem,1rem+4vw,4rem)', alignItems: 'center' }}>
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
              <div className="stat-huge" style={{ color: 'var(--primary-d)' }}>$41.5B</div>
              <p className="body-lg" style={{ marginTop: '.6rem', maxWidth: '32ch' }}>
                projected global genetic-testing market by 2030, up from $16.2B in 2023.
              </p>
              <div style={{ display: 'flex', gap: '.6rem', marginTop: '1.2rem', flexWrap: 'wrap' }}>
                <span className="pill"><span className="dot" /> 12.4% CAGR</span>
                <span className="pill"><span className="dot" /> recurring data events</span>
              </div>
              <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginTop: '1rem' }}>Coherent Market Insights, 2024</div>
            </motion.div>
            <motion.div className="card" style={{ padding: '2rem', background: 'var(--paper)' }} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .65 }}>
              <div className="display" style={{ fontSize: 'clamp(2rem,1rem+3vw,2.8rem)', color: 'var(--path-d)' }}>1 in 300</div>
              <p className="body-lg" style={{ marginTop: '.5rem' }}>
                people carry a hereditary-cancer variant, yet over <strong style={{ color: 'var(--ink)' }}>97% go undetected</strong>, and roughly 10% of common cancers are hereditary.
              </p>
              <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginTop: '1rem' }}>Population genomics literature, 2023</div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX center">
          <div className="mono-tag" style={{ justifyContent: 'center' }}><span className="dash" /> See it close</div>
          <h2 className="display display-mid" style={{ margin: '1rem auto 1.2rem', maxWidth: '18ch' }}>
            Watch the loop close, live.
          </h2>
          <p className="body-lg" style={{ maxWidth: '40ch', margin: '0 auto 2rem' }}>
            Rewind to 2019 and fast-forward: see the evidence change, the agent withhold the noise, and the family light up.
          </p>
          <Link to="/app" className="btn btn-primary">Open the simulator <ArrowRight size={18} /></Link>
        </div>
      </section>
    </div>
  );
}

/* ---- stat card ---- */
function StatCard({ num, t, src, accent }: { num: string; t: string; src: string; accent: string }) {
  return (
    <motion.div className="card" style={{ padding: '1.9rem' }} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .5 }}>
      <div className="display" style={{ color: accent, fontSize: 'clamp(2.2rem, 1rem + 3vw, 3.1rem)', lineHeight: 1 }}>{num}</div>
      <p style={{ color: 'var(--muted)', margin: '.8rem 0 0' }}>{t}</p>
      <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginTop: '1rem' }}>{src}</div>
    </motion.div>
  );
}

/* ---- tile ---- */
function Tile({ kicker, accent, icon, title, body, sketch }: { kicker: string; accent: string; icon: ReactNode; title: string; body: string; sketch: ReactNode }) {
  return (
    <motion.div className="tile" variants={{ h: { opacity: 0, y: 20 }, s: { opacity: 1, y: 0 } }} transition={{ duration: .5 }}>
      <div className="chip" style={{ marginBottom: '1.2rem' }}>{icon}</div>
      <div className="mono-tag" style={{ color: accent, gap: '.6rem' }}>{kicker}</div>
      <h3 className="display" style={{ fontSize: '1.5rem', margin: '.5rem 0 .7rem' }}>{title}</h3>
      <p style={{ color: 'var(--muted)' }}>{body}</p>
      <div className="vis">{sketch}</div>
    </motion.div>
  );
}

/* ---- mini sketches ---- */
function SketchSync() {
  return (
    <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
      {['ClinVar', 'gnomAD', 'AlphaMissense', 'AlphaFold'].map(s => (
        <span key={s} className="mono" style={{ fontSize: '.66rem', padding: '.3rem .55rem', borderRadius: 6, background: 'var(--primary-soft)', color: 'var(--primary-d)', border: '1px solid #bcccea' }}>{s}</span>
      ))}
    </div>
  );
}
function SketchAdjudicate() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
      <span className="badge badge-vus">VUS · 1★</span>
      <span style={{ color: 'var(--faint)' }}>→</span>
      <span className="mono" style={{ fontSize: '.7rem', color: 'var(--muted)' }}>withheld</span>
    </div>
  );
}
function SketchFanout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '.35rem' }}>
      {['Patient', 'Daughter · 1°', 'Sister · 1°'].map((s, i) => (
        <span key={s} className="mono" style={{ fontSize: '.68rem', color: i === 0 ? 'var(--muted)' : 'var(--path-d)', borderLeft: `3px solid ${i === 0 ? 'var(--line-2)' : 'var(--path)'}`, paddingLeft: '.5rem' }}>{s}</span>
      ))}
    </div>
  );
}
