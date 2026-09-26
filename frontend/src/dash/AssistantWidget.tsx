import { useEffect, useRef, useState } from 'react';
import { Sparkles, X, ArrowUp, ShieldCheck } from 'lucide-react';
import { assist } from '../api';

// A read-only, grounded "ask the data" helper. It forwards the current app
// context (assembled by AppDashboard from already-loaded, synthetic data) to the
// Flash explainer agent and shows the answer. It can explain, never act.

interface Msg { role: 'user' | 'bot'; text: string; grounded?: boolean }

const BASE_CHIPS = ['How does data get into Fivetran?', 'What is a VUS?', 'How do I add a patient?'];
const VIEW_CHIPS: Record<string, string[]> = {
  watchlist: ['What does the posterior mean?', 'Why is AlphaFold important?', 'What does the red mean in the 3D view?'],
  explorer: ['How fresh are the feeds?', 'What is the curated BigQuery view?', 'What does onboarding a gene do?'],
  graph: ['What is the knowledge graph showing?', 'Where does the review status come from?'],
  pedigree: ['Who are the at-risk relatives?', 'What is a cascade?'],
  approvals: ['Why is approval needed?', 'What is human-in-the-loop here?'],
  audit: ['What is recorded in the audit trail?', 'Is anything sent to patients?'],
  add: ['What happens when I add a patient?', 'Can I type any gene?'],
};

export default function AssistantWidget({ context, view }: { context: string; view: string }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bodyRef.current?.scrollTo({ top: 1e6, behavior: 'smooth' }); }, [msgs, busy]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const chips = [...(VIEW_CHIPS[view] ?? []), ...BASE_CHIPS].slice(0, 5);

  async function ask(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setInput('');
    setMsgs((m) => [...m, { role: 'user', text: question }]);
    setBusy(true);
    try {
      const r = await assist(question, context);
      setMsgs((m) => [...m, { role: 'bot', text: r.answer, grounded: r.grounded }]);
    } catch {
      setMsgs((m) => [...m, { role: 'bot', text: 'I had trouble reaching the engine just now. Please try again in a moment.', grounded: false }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <style>{`
        @keyframes uvchatpop { from { opacity:0; transform: translateY(10px) scale(.98) } to { opacity:1; transform:none } }
        @keyframes uvchatdot { 0%,80%,100% { opacity:.25 } 40% { opacity:1 } }
        .uv-chip:hover { background: var(--primary-soft) !important; color: var(--primary) !important; border-color: var(--primary) !important; }
        .uv-fab:hover { box-shadow: 0 8px 24px rgba(36,80,164,.42) !important; transform: translateY(-1px); }
      `}</style>

      {/* panel */}
      {open && (
        <div style={{
          position: 'fixed', right: 22, bottom: 88, zIndex: 1001,
          width: 374, maxWidth: 'calc(100vw - 44px)', height: 540, maxHeight: 'calc(100vh - 140px)',
          background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 16,
          boxShadow: 'var(--sh-lg)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
          animation: 'uvchatpop .18s ease both',
        }}>
          {/* header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', padding: '.85rem 1rem', borderBottom: '1px solid var(--line)', background: 'var(--paper)' }}>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: 'var(--primary-soft)', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
              <Sparkles size={16} color="var(--primary)" />
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: '.9rem' }}>Ask the data</div>
              <div style={{ fontSize: '.68rem', color: 'var(--faint)', fontFamily: 'var(--mono)' }}>Gemini Flash · read-only · grounded</div>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close assistant"
              style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--muted)', padding: 4, display: 'grid', placeItems: 'center' }}>
              <X size={17} />
            </button>
          </div>

          {/* body */}
          <div ref={bodyRef} style={{ flex: 1, overflowY: 'auto', padding: '.9rem 1rem', display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
            {msgs.length === 0 && (
              <div style={{ color: 'var(--muted)', fontSize: '.84rem', lineHeight: 1.55 }}>
                Hi — I can explain RelayCare's data, how it flows through Fivetran, and the genetics behind a case.
                I read what is on your screen, but I only explain; I never change anything or give medical advice.
                <div style={{ fontSize: '.72rem', color: 'var(--faint)', marginTop: '.5rem' }}>Try one of these:</div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%' }}>
                <div style={{
                  fontSize: '.84rem', lineHeight: 1.55, padding: '.55rem .75rem', borderRadius: 12,
                  whiteSpace: 'pre-wrap',
                  background: m.role === 'user' ? 'var(--primary)' : 'var(--paper-2)',
                  color: m.role === 'user' ? '#fff' : 'var(--ink)',
                  border: m.role === 'user' ? 'none' : '1px solid var(--line)',
                  borderBottomRightRadius: m.role === 'user' ? 4 : 12,
                  borderBottomLeftRadius: m.role === 'bot' ? 4 : 12,
                }}>{m.text}</div>
              </div>
            ))}
            {busy && (
              <div style={{ alignSelf: 'flex-start', display: 'flex', gap: 4, padding: '.6rem .75rem', background: 'var(--paper-2)', border: '1px solid var(--line)', borderRadius: 12 }}>
                {[0, 1, 2].map((d) => (
                  <span key={d} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--muted)', animation: `uvchatdot 1.2s ${d * 0.18}s infinite ease-in-out` }} />
                ))}
              </div>
            )}
          </div>

          {/* chips */}
          {msgs.length === 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.35rem', padding: '0 1rem .6rem' }}>
              {chips.map((c) => (
                <button key={c} className="uv-chip" onClick={() => ask(c)}
                  style={{ border: '1px solid var(--line-2)', background: 'var(--surface)', color: 'var(--muted)', borderRadius: 999, padding: '.32rem .6rem', fontSize: '.72rem', fontWeight: 600, cursor: 'pointer', transition: 'all .15s' }}>
                  {c}
                </button>
              ))}
            </div>
          )}

          {/* input */}
          <div style={{ borderTop: '1px solid var(--line)', padding: '.6rem .7rem', display: 'flex', alignItems: 'flex-end', gap: '.5rem', background: 'var(--paper)' }}>
            <textarea ref={inputRef} value={input} rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input); } }}
              placeholder="Ask about the data or the app…"
              style={{ flex: 1, resize: 'none', border: '1px solid var(--line-2)', borderRadius: 10, padding: '.5rem .6rem', fontSize: '.84rem', fontFamily: 'inherit', color: 'var(--ink)', background: 'var(--surface)', maxHeight: 90, lineHeight: 1.4 }} />
            <button onClick={() => ask(input)} disabled={busy || !input.trim()} aria-label="Send"
              style={{ border: 'none', background: input.trim() && !busy ? 'var(--primary)' : 'var(--line-2)', color: '#fff', borderRadius: 9, width: 34, height: 34, display: 'grid', placeItems: 'center', cursor: input.trim() && !busy ? 'pointer' : 'default', flexShrink: 0 }}>
              <ArrowUp size={17} />
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.35rem', padding: '0 1rem .55rem', fontSize: '.66rem', color: 'var(--faint)', fontFamily: 'var(--mono)' }}>
            <ShieldCheck size={11} /> Explains, never diagnoses · synthetic data only
          </div>
        </div>
      )}

      {/* floating button */}
      <button data-tour="assistant" className="uv-fab" onClick={() => setOpen((o) => !o)} aria-label="Ask the data assistant"
        style={{
          position: 'fixed', right: 22, bottom: 22, zIndex: 1001,
          height: 52, borderRadius: 999, border: 'none', cursor: 'pointer',
          background: 'var(--primary)', color: '#fff', display: 'flex', alignItems: 'center', gap: '.5rem',
          padding: open ? '0 14px' : '0 18px', fontWeight: 700, fontSize: '.85rem',
          boxShadow: '0 6px 18px rgba(36,80,164,.34)', transition: 'box-shadow .15s, transform .15s',
        }}>
        {open ? <X size={18} /> : <><Sparkles size={17} /> Ask the data</>}
      </button>
    </>
  );
}
