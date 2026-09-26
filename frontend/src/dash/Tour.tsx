import { useCallback, useEffect, useRef, useState } from 'react';
import { X, ChevronLeft, ChevronRight, Compass } from 'lucide-react';

// A dependency-free guided spotlight tour. Each step can switch the active view
// and prepopulate state (onEnter), then highlights a target element with a
// dimmed surround and a tooltip card. Prev / Next / Skip, keyboard, smooth.

export interface TourStep {
  selector?: string;      // [data-tour="..."] target; omit for a centered card
  title: string;
  body: string;
  onEnter?: () => void;   // switch tab, select a patient, etc.
  padding?: number;
}

interface Box { top: number; left: number; width: number; height: number }

const CARD_W = 340;

export default function Tour({ steps, open, onClose }: { steps: TourStep[]; open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const raf = useRef<number | null>(null);

  const step = steps[i];

  // find + measure the target for the current step, retrying while the tab renders
  const locate = useCallback(() => {
    if (!step) return;
    const pad = step.padding ?? 8;
    let tries = 0;
    const tick = () => {
      tries += 1;
      const el = step.selector ? document.querySelector<HTMLElement>(step.selector) : null;
      if (!step.selector) { setBox(null); return; }          // centered card
      if (el) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          // bring it into view, then settle the measurement
          const needScroll = r.top < 90 || r.bottom > window.innerHeight - 90;
          if (needScroll) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const settle = () => {
            const rr = el.getBoundingClientRect();
            setBox({ top: rr.top - pad, left: rr.left - pad, width: rr.width + pad * 2, height: rr.height + pad * 2 });
          };
          setTimeout(settle, needScroll ? 320 : 0);
          return;
        }
      }
      if (tries < 40) raf.current = requestAnimationFrame(tick);   // ~ up to 0.6s
      else setBox(null);
    };
    tick();
  }, [step]);

  // on step change: run side effects, then locate
  useEffect(() => {
    if (!open || !step) return;
    step.onEnter?.();
    const t = setTimeout(locate, 80);
    return () => { clearTimeout(t); if (raf.current) cancelAnimationFrame(raf.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, i]);

  // keep the spotlight pinned on resize / scroll
  useEffect(() => {
    if (!open) return;
    const on = () => locate();
    window.addEventListener('resize', on);
    window.addEventListener('scroll', on, true);
    return () => { window.removeEventListener('resize', on); window.removeEventListener('scroll', on, true); };
  }, [open, locate]);

  const next = useCallback(() => { if (i < steps.length - 1) setI(i + 1); else { onClose(); } }, [i, steps.length, onClose]);
  const prev = useCallback(() => { if (i > 0) setI(i - 1); }, [i]);
  const finish = useCallback(() => { onClose(); }, [onClose]);

  // reset to first step whenever reopened
  useEffect(() => { if (open) setI(0); }, [open]);

  // keyboard
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish();
      else if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, next, prev, finish]);

  if (!open || !step) return null;

  // tooltip position: centered if no target; else below the box (or above if no room)
  const vw = window.innerWidth, vh = window.innerHeight;
  let cardStyle: React.CSSProperties;
  if (!box) {
    cardStyle = { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' };
  } else {
    const below = box.top + box.height + 16 + 180 < vh;
    const top = below ? box.top + box.height + 14 : Math.max(16, box.top - 14 - 200);
    let left = box.left + box.width / 2 - CARD_W / 2;
    left = Math.min(Math.max(16, left), vw - CARD_W - 16);
    cardStyle = { top, left };
  }

  const last = i === steps.length - 1;

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 3000 }}>
      <style>{`@keyframes uvtourpop { from { opacity:0; transform: translateY(6px) } to { opacity:1 } }`}</style>

      {/* click catcher (blocks the page while guiding) */}
      <div onClick={(e) => e.stopPropagation()} style={{ position: 'absolute', inset: 0, cursor: 'default' }} />

      {/* spotlight (or full dim when centered) */}
      {box ? (
        <div style={{
          position: 'absolute', top: box.top, left: box.left, width: box.width, height: box.height,
          borderRadius: 12, boxShadow: '0 0 0 9999px rgba(13,18,32,.58)', border: '2px solid var(--primary)',
          pointerEvents: 'none', transition: 'top .35s cubic-bezier(.4,0,.2,1), left .35s cubic-bezier(.4,0,.2,1), width .35s, height .35s',
        }} />
      ) : (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(13,18,32,.58)' }} />
      )}

      {/* tooltip card */}
      <div style={{
        position: 'absolute', width: CARD_W, maxWidth: 'calc(100vw - 32px)',
        background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 14,
        boxShadow: 'var(--sh-lg)', padding: '1rem 1.1rem', ...cardStyle,
        animation: 'uvtourpop .22s ease both',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.45rem', fontFamily: 'var(--mono)', fontSize: '.64rem', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--primary)' }}>
            <Compass size={13} /> Tour · {i + 1} / {steps.length}
          </div>
          <button onClick={finish} aria-label="Skip tour" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--faint)', padding: 2, display: 'grid', placeItems: 'center' }}>
            <X size={15} />
          </button>
        </div>
        <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '.3rem' }}>{step.title}</div>
        <div style={{ fontSize: '.85rem', color: 'var(--muted)', lineHeight: 1.55 }}>{step.body}</div>

        {/* progress dots */}
        <div style={{ display: 'flex', gap: 4, margin: '.85rem 0 .7rem' }}>
          {steps.map((_, k) => (
            <span key={k} style={{ height: 4, flex: 1, borderRadius: 2, background: k <= i ? 'var(--primary)' : 'var(--line-2)', transition: 'background .2s' }} />
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.5rem' }}>
          <button onClick={finish} style={{ border: 'none', background: 'transparent', color: 'var(--faint)', fontSize: '.78rem', fontWeight: 600, cursor: 'pointer' }}>Skip</button>
          <div style={{ display: 'flex', gap: '.4rem' }}>
            <button onClick={prev} disabled={i === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '.2rem', border: '1px solid var(--line-2)', background: 'var(--surface)', color: i === 0 ? 'var(--line-2)' : 'var(--muted)', borderRadius: 8, padding: '.4rem .7rem', fontSize: '.8rem', fontWeight: 600, cursor: i === 0 ? 'default' : 'pointer' }}>
              <ChevronLeft size={14} /> Back
            </button>
            <button onClick={next}
              style={{ display: 'flex', alignItems: 'center', gap: '.2rem', border: 'none', background: 'var(--primary)', color: '#fff', borderRadius: 8, padding: '.4rem .85rem', fontSize: '.8rem', fontWeight: 700, cursor: 'pointer', boxShadow: '0 2px 8px rgba(36,80,164,.25)' }}>
              {last ? 'Done' : 'Next'} {!last && <ChevronRight size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
