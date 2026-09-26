import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, AlertTriangle, ShieldCheck, GitBranch, HeartPulse } from 'lucide-react';

const viewport = { once: true, margin: '-80px' };

function Clip({ src, caption, alt }: { src: string; caption: ReactNode; alt: string }) {
  const isVideo = src.endsWith('.mp4');

  return (
    <motion.figure className="card" style={{ padding: '.8rem', margin: 0, background: 'var(--paper)', overflow: 'hidden' }}
      initial={{ opacity: 0, y: 22 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
      {isVideo ? (
        <video src={src} autoPlay muted loop playsInline aria-label={alt}
          style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 'var(--r-sm)' }} />
      ) : (
        <img src={src} alt={alt}
          style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 'var(--r-sm)' }} />
      )}
      <figcaption className="mono" style={{ fontSize: '.72rem', color: 'var(--faint)', marginTop: '.7rem', textAlign: 'center' }}>{caption}</figcaption>
    </motion.figure>
  );
}

export default function MissionPage() {
  return (
    <div className="fade-in">
      {/* HEADER */}
      <section className="sec" style={{ paddingBottom: 'clamp(2rem,1rem+3vw,3.5rem)' }}>
        <div className="wrapX" style={{ maxWidth: '900px' }}>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }}>
            <div className="mono-tag"><span className="dash" /> The mission</div>
            <h1 className="display display-fluid" style={{ margin: '1.3rem 0 1.4rem', maxWidth: '15ch' }}>
              The loop that <span className="emph">never closes</span>.
            </h1>
            <p className="body-lg" style={{ maxWidth: '60ch' }}>
              A genetic panel often returns a Variant of Uncertain Significance, one the lab can’t yet call benign or
              dangerous. Clinically, “uncertain” means do nothing. But the evidence does not stand still, and no one is
              watching on the patient’s behalf when it moves.
            </p>
          </motion.div>
        </div>
      </section>

      {/* WHY THIS MATTERS — the founder's personal connection */}
      <section className="sec" style={{ paddingTop: 0 }}>
        <div className="wrapX" style={{ maxWidth: '900px' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> Why this matters to me · 01</div>
            <h2 className="display display-mid" style={{ margin: '1rem 0 1.3rem', maxWidth: '20ch' }}>This is personal for me.</h2>
            <blockquote className="pullquote" style={{ maxWidth: '60ch' }}>
              My mom has a PhD and works in cancer genetics. I grew up seeing how much careful work goes into deciding which
              variants matter, and how easily a changed interpretation can fail to reach the family it was about.
            </blockquote>
            <p className="body-lg" style={{ maxWidth: '58ch', marginTop: '1.4rem' }}>
              The <strong style={{ color: 'var(--ink)' }}>interpretation</strong> belongs with trained clinicians. I built
              RelayCare to help keep track of what changed, who may be affected, and what still needs a human decision.
            </p>
          </motion.div>
        </div>
      </section>

      {/* DIANE, case file + the animation */}
      <section className="sec" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX thesis-grid" style={{ alignItems: 'center' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> A true-to-life case · 02</div>
            <h2 className="display display-mid" style={{ margin: '1rem 0 1.3rem' }}>Diane, 44.</h2>
            <div className="body-lg" style={{ display: 'grid', gap: '1rem', maxWidth: '56ch' }}>
              <p>In 2019 she had surgery for colorectal cancer. Her germline panel returned a <strong style={{ color: 'var(--ink)' }}>VUS in MLH1</strong>, a Lynch syndrome gene. Nothing was done. Her oncologist said, <em>“if it ever changes, we’ll let you know.”</em></p>
              <p>It changed. In 2023 a ClinGen expert panel reclassified that exact variant to <strong style={{ color: 'var(--ink)' }}>likely pathogenic</strong>. The update went public. It never reached Diane.</p>
            </div>
          </motion.div>

          <motion.div className="card" style={{ padding: 0, overflow: 'hidden' }} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .7 }}>
            <div style={{ background: 'var(--primary-d)', color: '#fff', padding: '.7rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="mono" style={{ fontSize: '.72rem', letterSpacing: '.08em', fontWeight: 600 }}>CASE FILE</span>
              <span className="mono" style={{ fontSize: '.72rem', opacity: .85 }}>MLH1 · Lynch</span>
            </div>
            <div style={{ padding: '1.8rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '.8rem', marginBottom: '1.2rem' }}>
                <span className="badge badge-vus">VUS · 2019</span>
                <span style={{ color: 'var(--faint)' }}>→</span>
                <span className="badge badge-path">Likely pathogenic · 2023</span>
              </div>
              <div style={{ background: 'var(--path-soft)', border: '1px solid #f0b8bd', borderRadius: 'var(--r-sm)', padding: '1.2rem 1.3rem', display: 'flex', gap: '.9rem' }}>
                <AlertTriangle size={22} color="var(--path-d)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <p style={{ color: 'var(--path-d)', fontSize: '1rem', lineHeight: 1.55, fontWeight: 500 }}>
                  Her 22-year-old daughter could have started colonoscopies the day the variant flipped. She later
                  presented with a tumour Lynch surveillance is built to catch early. The loop never closed.
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        <div className="wrapX" style={{ marginTop: '2.4rem' }}>
          <Clip src="/images/relaycare-family-loop.png"
            alt="Clinician and family member reviewing a genetic evidence timeline together"
            caption="2019 → 2023 · the variant flips, the update reaches the public database, and the link to Diane never completes" />
        </div>
      </section>

      {/* THE COST — numbers */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX" style={{ display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: 'clamp(2rem,1rem+4vw,4.5rem)', alignItems: 'center' }} >
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> The cost · 03</div>
            <div className="stat-huge" style={{ marginTop: '1.1rem' }}>24%</div>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .65 }}>
            <p className="body-lg" style={{ maxWidth: '52ch', marginBottom: '.6rem' }}>
              of genetic counsellors have received a reclassified VUS for a patient who had <span className="emph">already died</span>, with no guideline for what happens next.
            </p>
            <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginBottom: '1.4rem' }}>Lascurain et al., J. Genetic Counseling 2024</div>
            <p className="body-lg" style={{ maxWidth: '54ch' }}>
              That delay isn’t a flaw; it’s the reason this matters. A germline variant that flips is a <strong style={{ color: 'var(--ink)' }}>family event</strong>, yet <strong style={{ color: 'var(--ink)' }}>nearly 1 in 3</strong> at-risk relatives are never even told they may carry it, and reclassification changes management in <strong style={{ color: 'var(--ink)' }}>up to 41%</strong> of patients.
            </p>
            <div className="mono" style={{ fontSize: '.7rem', color: 'var(--faint)', marginTop: '.9rem' }}>Ahsan et al., PEC Innovation 2023 · Makhnoon et al., Cancer Medicine 2023</div>
          </motion.div>
        </div>
      </section>

      {/* ASYMMETRIC BY DESIGN + the moat clip */}
      <section className="sec">
        <div className="wrapX thesis-grid" style={{ alignItems: 'center' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={viewport} transition={{ duration: .6 }}>
            <div className="mono-tag"><span className="dash" /> The judgement · 04</div>
            <h2 className="display display-mid" style={{ margin: '1rem 0 1.3rem', maxWidth: '22ch' }}>Correct triage, not an alarm on every change.</h2>
            <div className="body-lg" style={{ display: 'grid', gap: '1rem', maxWidth: '56ch' }}>
              <p>
                Most reclassifications are <strong style={{ color: 'var(--ink)' }}>downgrades</strong>. So RelayCare surfaces the
                rare, life-changing upgrade loudly, and handles the common downgrade as quiet reassurance.
              </p>
              <p>
                Two variants can carry identical molecular evidence, the same rarity, the same score, the same posterior, yet
                warrant <em>opposite</em> actions, decided on the quality of the evidence behind them. That judgement is why
                RelayCare is an <strong style={{ color: 'var(--ink)' }}>agent</strong>, not a script.
              </p>
            </div>
          </motion.div>
          <Clip src="/images/relaycare-evidence-judgement.png"
            alt="Genetics reviewers comparing two evidence files with different review-quality signals"
            caption="Identical molecular evidence, opposite verdict, decided on review quality, the call a threshold cannot make" />
        </div>
      </section>

      {/* WHAT IT IS, AND ISN'T */}
      <section className="sec" style={{ background: 'var(--paper-2)', borderTop: '1px solid var(--line)' }}>
        <div className="wrapX">
          <div className="mono-tag"><span className="dash" /> Honestly · 05</div>
          <h2 className="display display-mid" style={{ margin: '1rem 0 2.2rem', maxWidth: '22ch' }}>What RelayCare is, and what it isn’t.</h2>
          <div className="grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '1.2rem' }}>
            <div className="tile">
              <div className="chip" style={{ marginBottom: '1rem' }}><ShieldCheck size={20} color="var(--benign)" /></div>
              <h3 className="display" style={{ fontSize: '1.3rem', marginBottom: '.5rem' }}>Draft-only, human-in-the-loop</h3>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>Clinical decision support, not a diagnostic device. Every output is a draft a clinician reviews and sends. The agent’s line is notification, never autonomous action.</p>
            </div>
            <div className="tile">
              <div className="chip" style={{ marginBottom: '1rem' }}><GitBranch size={20} color="var(--primary)" /></div>
              <h3 className="display" style={{ fontSize: '1.3rem', marginBottom: '.5rem' }}>Kinship-first, disease-agnostic</h3>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>The beneficiary is often the living relative, not only the proband. The same open loop fails across hereditary cancer and rare disease alike; type any gene and it resolves.</p>
            </div>
            <div className="tile">
              <div className="chip" style={{ marginBottom: '1rem' }}><HeartPulse size={20} color="var(--path)" /></div>
              <h3 className="display" style={{ fontSize: '1.3rem', marginBottom: '.5rem' }}>Synthetic patients, real variants</h3>
              <p style={{ color: 'var(--muted)', fontSize: '.94rem' }}>A research prototype: the patients are synthetic, so no real patient information is ever handled; the variants and their reclassification histories are real. Privacy by design.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="sec center">
        <div className="wrapX">
          <h2 className="display display-mid" style={{ marginBottom: '1.4rem', maxWidth: '20ch', marginInline: 'auto' }}>See how RelayCare closes the loop.</h2>
          <Link to="/app" className="btn btn-primary">Open the simulator <ArrowRight size={18} /></Link>
        </div>
      </section>
    </div>
  );
}
