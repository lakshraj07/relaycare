import type { PosteriorBreakdown as BD } from '../api';

// Transparent points -> odds -> posterior waterfall. Shows exactly what goes into
// the verdict: starting from the prior, each cited ACMG item moves the running
// point total and the calibrated posterior, ending at the band. This is the
// "maths made legible" panel (Tavtigian 2018/2020 point-based Bayesian ACMG).

const mono: React.CSSProperties = { fontFamily: 'var(--mono)' };

function posColor(p: number): string {
  if (p >= 0.9) return 'var(--path-d)';
  if (p <= 0.1) return 'var(--benign)';
  return 'var(--thread-d)';
}

function Bar({ p, delta }: { p: number; delta: number }) {
  // a 0..1 track with the 0.90 actionable line and a marker at the running posterior
  const edge = delta > 0 ? 'var(--path)' : delta < 0 ? 'var(--benign)' : 'var(--line-2)';
  return (
    <span style={{ position: 'relative', display: 'block', height: 8, borderRadius: 999, background: 'var(--paper-2)', overflow: 'visible' }}>
      <span style={{ position: 'absolute', inset: 0, width: `${p * 100}%`, borderRadius: 999, background: 'linear-gradient(90deg,var(--benign),#d7c98f 45%,#e7b06a 60%,var(--path))', opacity: 0.85 }} />
      <span style={{ position: 'absolute', top: -2, left: '90%', width: 1.5, height: 12, background: 'rgba(23,26,43,.4)' }} />
      <span style={{ position: 'absolute', top: -2, left: `calc(${p * 100}% - 1px)`, width: 2.5, height: 12, background: edge, borderRadius: 2, transition: 'left .6s cubic-bezier(.2,.8,.2,1)' }} />
    </span>
  );
}

function Row({ code, label, delta, cumPoints, posterior, detail }: {
  code: string; label?: string; delta: number; cumPoints: number; posterior: number; detail?: string;
}) {
  const sign = delta > 0 ? '+' : '';
  const chipBg = delta > 0 ? 'var(--path-bg)' : delta < 0 ? 'var(--benign-bg)' : 'var(--paper-2)';
  const chipFg = delta > 0 ? 'var(--path-d)' : delta < 0 ? 'var(--benign)' : 'var(--faint)';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '74px 1fr 88px', gap: '.6rem', alignItems: 'center', padding: '.32rem 0', borderTop: '1px solid var(--line)' }}>
      <div>
        <span style={{ ...mono, fontSize: '.66rem', fontWeight: 700, padding: '.12rem .4rem', borderRadius: 6, background: chipBg, color: chipFg }}>
          {code}{delta !== 0 ? ` ${sign}${delta}` : ''}
        </span>
      </div>
      <div style={{ minWidth: 0 }}>
        <Bar p={posterior} delta={delta} />
        {(label || detail) && (
          <div style={{ ...mono, fontSize: '.62rem', color: 'var(--faint)', marginTop: '.18rem', overflowWrap: 'anywhere', lineHeight: 1.35 }}>
            {label || detail}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <span style={{ ...mono, fontSize: '.78rem', fontWeight: 600, color: posColor(posterior) }}>{posterior.toFixed(2)}</span>
        <span style={{ ...mono, fontSize: '.6rem', color: 'var(--faint)', display: 'block' }}>{cumPoints >= 0 ? '+' : ''}{cumPoints} pt</span>
      </div>
    </div>
  );
}

export default function PosteriorBreakdown({ breakdown }: { breakdown: BD }) {
  const b = breakdown;
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '.4rem' }}>
        <span style={{ ...mono, fontSize: '.64rem', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--faint)' }}>
          points &rarr; odds &rarr; posterior
        </span>
        <span style={{ ...mono, fontSize: '.64rem', color: 'var(--faint)' }}>
          odds path {b.odds_path}:1 &middot; prior {b.prior}
        </span>
      </div>

      <div style={{ marginTop: '.4rem' }}>
        <Row code="prior" label="base rate before evidence" delta={0} cumPoints={0} posterior={b.prior_posterior} />
        {b.steps.map((s, i) => (
          <Row key={i} code={s.code} delta={s.points} cumPoints={s.cumulative_points}
            posterior={s.cumulative_posterior} detail={`${s.source}${s.detail ? ' · ' + s.detail : ''}`} />
        ))}
        {b.steps.length === 0 && (
          <div style={{ ...mono, fontSize: '.7rem', color: 'var(--faint)', padding: '.4rem 0' }}>
            no molecular criteria met &mdash; posterior stays at the prior
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '.5rem', paddingTop: '.5rem', borderTop: '1.5px solid var(--line-2)' }}>
        <span style={{ ...mono, fontSize: '.66rem', color: 'var(--muted)' }}>
          {b.total_points >= 0 ? '+' : ''}{b.total_points} pts &middot; {b.is_actionable ? 'at/over' : `${b.points_to_actionable} from`} the {b.actionable_line.posterior} line
        </span>
        <span style={{ fontFamily: 'var(--serif)', fontSize: '1.3rem', color: posColor(b.posterior) }}>{b.posterior.toFixed(2)}</span>
      </div>
    </div>
  );
}
