import { useRef, type ReactNode } from 'react';
import { motion, useScroll, useTransform, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

type Panel = { n: string; tag: string; title: string; body: string; accent: string; vis: ReactNode };

/* ============================================================
   Polished clinical SVG visuals (gradients + depth, light)
   ============================================================ */

const C = {
  primary: '#2450a4', primaryD: '#173268', primaryBright: '#3163c4', primarySoft: '#e9eef9',
  conflict: '#4f93d6', conflictBg: '#e9f1fb',
  path: '#c62833', pathD: '#9c1f29', pathSoft: '#fbe4e6',
  benign: '#2f8a5b',
  ink: '#171a2b', muted: '#586173', faint: '#8a92a2', line: '#e7e2d7', line2: '#dcd6c9',
};

function Star({ x, y, r, fill }: { x: number; y: number; r: number; fill: string }) {
  const pts = Array.from({ length: 10 }, (_, i) => {
    const ang = (Math.PI / 5) * i - Math.PI / 2;
    const rad = i % 2 === 0 ? r : r * 0.45;
    return `${x + rad * Math.cos(ang)},${y + rad * Math.sin(ang)}`;
  }).join(' ');
  return <polygon points={pts} fill={fill} />;
}

function VisWatch() {
  const sources = [
    { s: 'ClinVar', x: 52, y: 48 }, { s: 'gnomAD', x: 288, y: 48 },
    { s: 'AlphaMissense', x: 52, y: 212 }, { s: 'AlphaFold', x: 288, y: 212 },
  ];
  return (
    <svg viewBox="0 0 340 260" width="100%" style={{ maxWidth: 380 }} fill="none">
      <defs>
        <linearGradient id="wHub" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={C.primaryBright} /><stop offset="1" stopColor={C.primaryD} />
        </linearGradient>
        <filter id="wShadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#173268" floodOpacity="0.18" />
        </filter>
      </defs>
      {sources.map(({ s, x, y }) => (
        <g key={s}>
          <path d={`M${x} ${y} C ${(x + 170) / 2} ${y}, ${(x + 170) / 2} 130, 170 130`} stroke={C.conflict} strokeWidth="1.6" strokeDasharray="2 6" opacity="0.7" />
          <rect x={x - 38} y={y - 15} width="76" height="30" rx="9" fill="#fff" stroke={C.line2} filter="url(#wShadow)" />
          <circle cx={x - 24} cy={y} r="3.4" fill={C.conflict} />
          <text x={x + 4} y={y + 4} textAnchor="middle" fontSize="11.5" fontFamily="monospace" fontWeight="600" fill={C.primaryD}>{s}</text>
        </g>
      ))}
      {/* hub cylinder */}
      <g filter="url(#wShadow)">
        <ellipse cx="170" cy="112" rx="42" ry="14" fill="url(#wHub)" />
        <path d="M128 112 v34 c0 7.7 18.8 14 42 14 s42 -6.3 42 -14 v-34" fill="url(#wHub)" />
        <ellipse cx="170" cy="112" rx="42" ry="14" fill={C.primaryBright} />
        <ellipse cx="170" cy="130" rx="42" ry="14" fill="none" stroke="#fff" strokeWidth="1.4" opacity="0.45" />
      </g>
      <circle cx="170" cy="130" r="58" stroke={C.primary} strokeWidth="1.4" opacity="0.18" />
      <text x="170" y="240" textAnchor="middle" fontSize="11" fontFamily="monospace" fill={C.faint}>continuous sync</text>
    </svg>
  );
}

function VisDetect() {
  return (
    <svg viewBox="0 0 340 260" width="100%" style={{ maxWidth: 380 }} fill="none">
      <defs>
        <linearGradient id="dFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={C.conflict} stopOpacity="0.35" /><stop offset="1" stopColor={C.conflict} stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="14" y="18" width="312" height="206" rx="14" fill="#fff" stroke={C.line} />
      {[70, 110, 150, 190].map(y => <line key={y} x1="34" y1={y} x2="306" y2={y} stroke={C.line} strokeWidth="1" />)}
      {/* area + line: flat then spike at 2023 */}
      <path d="M34 190 L150 190 L196 56 L226 190 L306 190 Z" fill="url(#dFill)" />
      <path d="M34 190 L150 190 L196 56 L226 190 L306 190" stroke={C.conflict} strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" />
      <line x1="196" y1="56" x2="196" y2="206" stroke={C.path} strokeWidth="1.4" strokeDasharray="3 4" opacity="0.6" />
      <circle cx="196" cy="56" r="6.5" fill="#fff" stroke={C.path} strokeWidth="3" />
      <g>
        <rect x="170" y="30" width="52" height="20" rx="10" fill={C.pathSoft} stroke="#f0b8bd" />
        <text x="196" y="44" textAnchor="middle" fontSize="11" fontWeight="700" fontFamily="monospace" fill={C.pathD}>Δ 2023</text>
      </g>
      <text x="40" y="216" fontSize="10.5" fontFamily="monospace" fill={C.faint}>2019</text>
      <text x="290" y="216" fontSize="10.5" fontFamily="monospace" fill={C.faint}>2026</text>
    </svg>
  );
}

function VisAdjudicate() {
  return (
    <svg viewBox="0 0 340 260" width="100%" style={{ maxWidth: 380 }} fill="none">
      <defs>
        <filter id="aShadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="3" stdDeviation="5" floodColor="#173268" floodOpacity="0.16" />
        </filter>
      </defs>
      {/* post + base */}
      <line x1="170" y1="44" x2="170" y2="206" stroke={C.ink} strokeWidth="3" strokeLinecap="round" />
      <path d="M146 206 h48 l-24 20 z" fill={C.ink} />
      <circle cx="170" cy="44" r="5" fill={C.ink} />
      {/* beam tilted toward 3 star (right heavy) */}
      <line x1="74" y1="60" x2="266" y2="84" stroke={C.muted} strokeWidth="3" strokeLinecap="round" />
      {/* left pan: 1 star, light/high */}
      <line x1="74" y1="60" x2="74" y2="96" stroke={C.line2} strokeWidth="1.6" />
      <g filter="url(#aShadow)"><rect x="34" y="96" width="80" height="38" rx="10" fill="#fff" stroke={C.line2} /></g>
      <Star x={52} y={115} r={8} fill="#d9b24a" />
      <text x="78" y="119" textAnchor="middle" fontSize="10.5" fontFamily="monospace" fill={C.muted}>held</text>
      {/* right pan: 3 star, heavy/low */}
      <line x1="266" y1="84" x2="266" y2="138" stroke={C.path} strokeWidth="1.6" />
      <g filter="url(#aShadow)"><rect x="222" y="138" width="92" height="42" rx="10" fill={C.pathSoft} stroke="#f0b8bd" /></g>
      <Star x={240} y={159} r={7} fill={C.path} /><Star x={258} y={159} r={7} fill={C.path} /><Star x={276} y={159} r={7} fill={C.path} />
      <text x="268" y="174" textAnchor="middle" fontSize="10" fontFamily="monospace" fontWeight="700" fill={C.pathD}>actionable</text>
    </svg>
  );
}

function VisMatch() {
  const ring = (cx: number, cy: number) => <circle cx={cx} cy={cy} r="26" stroke={C.path} strokeWidth="1.4" opacity="0.3" />;
  return (
    <svg viewBox="0 0 340 260" width="100%" style={{ maxWidth: 380 }} fill="none">
      <defs>
        <filter id="mShadow" x="-40%" y="-40%" width="180%" height="180%">
          <feDropShadow dx="0" dy="3" stdDeviation="5" floodColor="#173268" floodOpacity="0.16" />
        </filter>
      </defs>
      {/* connectors */}
      <path d="M100 70 H240 M170 70 V112 M100 70 V150 M240 70 V150" stroke={C.line2} strokeWidth="2" fill="none" />
      {/* proband (top, neutral) */}
      <g filter="url(#mShadow)"><circle cx="170" cy="56" r="18" fill="#fff" stroke={C.muted} strokeWidth="2.5" /></g>
      <text x="170" y="30" textAnchor="middle" fontSize="10.5" fontFamily="monospace" fill={C.muted}>proband</text>
      {/* sister (left, at-risk) */}
      {ring(100, 166)}
      <g filter="url(#mShadow)"><circle cx="100" cy="166" r="18" fill={C.pathSoft} stroke={C.path} strokeWidth="2.5" /></g>
      <text x="100" y="202" textAnchor="middle" fontSize="10.5" fontFamily="monospace" fill={C.pathD}>sister</text>
      {/* daughter (right, at-risk) */}
      {ring(240, 166)}
      <g filter="url(#mShadow)"><circle cx="240" cy="166" r="18" fill={C.pathSoft} stroke={C.path} strokeWidth="2.5" /></g>
      <text x="240" y="202" textAnchor="middle" fontSize="10.5" fontFamily="monospace" fill={C.pathD}>daughter</text>
      <text x="170" y="238" textAnchor="middle" fontSize="11" fontFamily="monospace" fill={C.faint}>2 at-risk relatives</text>
    </svg>
  );
}

function VisDraft() {
  return (
    <svg viewBox="0 0 340 260" width="100%" style={{ maxWidth: 380 }} fill="none">
      <defs>
        <filter id="fShadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="6" stdDeviation="9" floodColor="#173268" floodOpacity="0.2" />
        </filter>
      </defs>
      <g filter="url(#fShadow)">
        <rect x="96" y="26" width="148" height="208" rx="12" fill="#fff" stroke={C.line2} />
        <rect x="96" y="26" width="148" height="34" rx="12" fill={C.primaryD} />
        <rect x="96" y="48" width="148" height="12" fill={C.primaryD} />
        <text x="116" y="48" fontSize="11" fontFamily="monospace" fontWeight="700" fill="#fff">RECONTACT</text>
      </g>
      {[80, 98, 116, 134].map(y => <rect key={y} x="116" y={y} width="108" height="6" rx="3" fill={C.line2} />)}
      <rect x="116" y="152" width="70" height="6" rx="3" fill={C.line2} />
      <rect x="116" y="178" width="92" height="24" rx="7" fill={C.primarySoft} stroke="#bcccea" />
      <text x="162" y="194" textAnchor="middle" fontSize="10.5" fontFamily="monospace" fill={C.primaryD}>FHIR · Task</text>
      {/* DRAFT stamp */}
      <g transform="rotate(-11 214 70)">
        <rect x="166" y="52" width="96" height="34" rx="7" fill="#fff" stroke={C.benign} strokeWidth="2.5" />
        <text x="214" y="74" textAnchor="middle" fontSize="13.5" fontWeight="800" fontFamily="monospace" fill={C.benign}>DRAFT</text>
      </g>
    </svg>
  );
}

const panels: Panel[] = [
  { n: '01', tag: 'Watch', accent: C.primary, vis: <VisWatch />, title: 'The evidence never stops moving', body: 'Fivetran keeps ClinVar, gnomAD and AlphaMissense in continuous sync, driven through the real MCP server. The Scout reads freshness, triggers re-syncs, and runs an auditable delta against the clinic’s historical VUS registry.' },
  { n: '02', tag: 'Detect', accent: C.conflict, vis: <VisDetect />, title: 'A variant quietly changes class', body: 'Years after the report, a Variant of Uncertain Significance is reassessed. The Scout catches the delta the moment the feed updates, with no human having to remember to look.' },
  { n: '03', tag: 'Adjudicate', accent: C.primary, vis: <VisAdjudicate />, title: 'Is the change actually real?', body: 'The Arbiter weighs review status, resolves conflicting submissions, applies ACMG and gene-tier logic, and withholds a low-confidence flip. The part no rules engine can do.' },
  { n: '04', tag: 'Match', accent: C.path, vis: <VisMatch />, title: 'Find everyone who carries it', body: 'On a confirmed, actionable upgrade, RelayCare locates the patient and the at-risk first-degree relatives in the FHIR pedigree. A germline variant is a family event.' },
  { n: '05', tag: 'Draft', accent: C.path, vis: <VisDraft />, title: 'Close the loop, for review', body: 'A drafted recontact and Kinship-testing fan-out, written back as FHIR Task and Communication (intent: proposal). Clinician reviewed, never sent autonomously.' },
];

function PanelInner({ p }: { p: Panel }) {
  return (
    <div className="fpanel-grid" style={{ display: 'grid', gridTemplateColumns: '1.05fr .95fr', gap: 'clamp(1.5rem,1rem+3vw,3.5rem)', alignItems: 'center', width: '100%', maxWidth: 1020 }}>
      <div>
        <div className="fnum" style={{ color: p.accent, opacity: .24 }}>{p.n}</div>
        <div className="mono-tag" style={{ marginTop: '.4rem' }}>
          <span className="dash" style={{ background: p.accent }} /> {p.tag} · step {p.n}
        </div>
        <h3 className="display display-mid" style={{ margin: '1rem 0 1.1rem' }}>{p.title}</h3>
        <p className="body-lg" style={{ maxWidth: '48ch' }}>{p.body}</p>
      </div>
      <div style={{ display: 'grid', placeItems: 'center' }}>
        <div className="card" style={{ padding: '1.6rem', width: '100%', maxWidth: 430, display: 'grid', placeItems: 'center', background: 'linear-gradient(180deg,#ffffff,#fbfaf6)' }}>{p.vis}</div>
      </div>
    </div>
  );
}

const Header = (
  <div className="wrapX" style={{ paddingTop: '2rem' }}>
    <div className="mono-tag"><span className="dash" /> The loop · 02</div>
    <h2 className="display display-mid" style={{ marginTop: '.7rem', maxWidth: '20ch' }}>
      From a moving database to a phone call that saves a life
    </h2>
  </div>
);

export default function Funnel() {
  const ref = useRef<HTMLDivElement | null>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] });
  const x = useTransform(scrollYProgress, [0, 1], ['0vw', `-${(panels.length - 1) * 100}vw`]);

  if (reduce) {
    return (
      <section id="loop" className="sec" style={{ background: 'var(--paper-2)' }}>
        {Header}
        <div className="wrapX" style={{ display: 'grid', gap: '1.4rem', marginTop: '2.5rem' }}>
          {panels.map(p => <div key={p.n} className="card" style={{ padding: '2rem' }}><PanelInner p={p} /></div>)}
        </div>
      </section>
    );
  }

  return (
    <section id="loop" ref={ref} style={{ height: `${panels.length * 100}vh`, position: 'relative', background: 'var(--paper-2)' }}>
      <div className="hpin">
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 3 }}>{Header}</div>
        <motion.div className="hpin-track" style={{ x }}>
          {panels.map((p, i) => (
            <div key={p.n} className="fpanel" style={{ borderRight: i < panels.length - 1 ? '1px solid var(--line)' : 'none' }}>
              <PanelInner p={p} />
            </div>
          ))}
        </motion.div>
        <div style={{ position: 'absolute', bottom: '2.4rem', left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: '.5rem', zIndex: 3 }}>
          {panels.map(p => <span key={p.n} style={{ height: 6, width: 20, borderRadius: 6, background: p.accent, opacity: .4 }} />)}
        </div>
        <div className="wrapX hide-sm" style={{ position: 'absolute', bottom: '2.1rem', right: 0, zIndex: 3, color: 'var(--faint)', fontSize: '.78rem', display: 'flex', justifyContent: 'flex-end', gap: '.4rem', alignItems: 'center' }}>
          scroll <ArrowRight size={14} />
        </div>
      </div>
    </section>
  );
}
