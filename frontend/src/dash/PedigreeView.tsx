import { useEffect, useMemo, useState } from 'react';
import { Mail, PhoneCall, AlertTriangle, Check, ChevronDown } from 'lucide-react';
import { getPedigree, type Pedigree, type PedigreeMember, type CohortRow } from '../api';
import { card, mono, tag, eyebrow } from './ui';

export default function PedigreeView({ patientId, cohort }: { patientId: string; cohort: CohortRow[] }) {
  // selectable families = the reclassified carriers (each anchors a pedigree)
  const families = useMemo(
    () => cohort.filter((r) => r.reclassified).map((r) => ({ id: r.patient_id, name: r.patient_name, gene: r.gene, hgvs: r.hgvs_c })),
    [cohort],
  );
  const [selId, setSelId] = useState(patientId);
  useEffect(() => { setSelId(patientId); }, [patientId]);

  const [ped, setPed] = useState<Pedigree | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drafted, setDrafted] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setPed(null); setErr(null); setDrafted({});
    getPedigree(selId).then(setPed).catch((e) => setErr(String(e.message || e)));
  }, [selId]);

  const proband = ped?.members.find((m) => m.relationship === 'proband');
  const relatives = ped?.members.filter((m) => m.relationship !== 'proband') ?? [];

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {/* family switcher */}
      <div style={{ ...card, padding: '.7rem .9rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={eyebrow}>Family</div>
        <div style={{ position: 'relative', minWidth: 260 }}>
          <select value={selId} onChange={(e) => setSelId(e.target.value)}
            style={{
              appearance: 'none', width: '100%', border: '1px solid var(--line)', borderRadius: 9, background: 'var(--paper)',
              padding: '.5rem 2rem .5rem .7rem', fontSize: '.88rem', fontWeight: 600, fontFamily: 'var(--sans)', cursor: 'pointer',
            }}>
            {families.map((f) => <option key={f.id} value={f.id}>{f.name} — {f.gene} {f.hgvs}</option>)}
          </select>
          <ChevronDown size={15} color="var(--muted)" style={{ position: 'absolute', right: 10, top: 11, pointerEvents: 'none' }} />
        </div>
        {proband && <span style={{ ...mono({ fontSize: '.72rem' }), color: 'var(--faint)' }}>{ped?.members.length} member(s) on file</span>}
      </div>

      {err && <div style={{ ...card, ...tag('var(--path-d)', 'var(--path-bg)'), whiteSpace: 'normal' }}>Error: {err}</div>}
      {!ped && !err && <div style={{ ...card, color: 'var(--faint)' }}>loading pedigree…</div>}

      {ped && (
        <div style={card}>
          <div style={eyebrow}>Cascade map</div>
          <div style={{ fontSize: '.84rem', color: 'var(--muted)', marginTop: '.3rem' }}>
            The proband's variant has been reclassified. At-risk first-degree relatives should be offered counselling and
            predictive testing. Relatives with no contact route on file are the recontact gap.
          </div>

          {/* tree */}
          <div style={{ marginTop: '1.6rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {proband && <PersonCard m={proband} drafted={drafted} setDrafted={setDrafted} />}
            {relatives.length > 0 && (
              <>
                <Connector />
                <div style={{ height: 2, width: 'min(720px, 94%)', background: 'var(--line-2)', borderRadius: 2 }} />
                <div style={{ display: 'flex', gap: '1.1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                  {relatives.map((m) => (
                    <div key={m.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <Connector />
                      <PersonCard m={m} drafted={drafted} setDrafted={setDrafted} />
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* recontact summary */}
          <div style={{ marginTop: '1.4rem', display: 'flex', gap: '1.6rem', flexWrap: 'wrap', borderTop: '1px solid var(--line)', paddingTop: '1rem' }}>
            <Stat n={`${ped.needs_contact.length}`} l="at-risk relatives to offer testing" />
            <Stat n={`${ped.needs_contact.filter((m) => !m.email && !m.phone).length}`} l="with no contact route" tone="path" />
            <Stat n={`${Object.values(drafted).filter(Boolean).length}`} l="recontacts drafted" tone="thread" />
          </div>

          {ped.history.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={eyebrow}>Family history (FHIR FamilyMemberHistory)</div>
              <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginTop: '.5rem' }}>
                {ped.history.map((h, i) => (
                  <span key={i} style={tag('var(--muted)', 'var(--paper-2)')}>
                    {h.relationship}{h.deceased ? ' †' : ''}{h.condition ? ` · ${h.condition}` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Connector() {
  return <div style={{ width: 2, height: 22, background: 'var(--line-2)' }} />;
}

function Stat({ n, l, tone }: { n: string; l: string; tone?: 'path' | 'thread' }) {
  const col = tone === 'path' ? 'var(--path-d)' : tone === 'thread' ? 'var(--thread-d)' : 'var(--ink)';
  return (
    <div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: '1.5rem', color: col, lineHeight: 1 }}>{n}</div>
      <div style={{ fontSize: '.72rem', color: 'var(--muted)', marginTop: '.2rem', maxWidth: 160 }}>{l}</div>
    </div>
  );
}

function PersonCard({ m, drafted, setDrafted }: {
  m: PedigreeMember; drafted: Record<string, boolean>; setDrafted: (f: (d: Record<string, boolean>) => Record<string, boolean>) => void;
}) {
  const isProband = m.relationship === 'proband';
  const status = drafted[m.id] ? 'draft prepared' : m.recontact_status;
  const sc = status === 'draft prepared' ? { fg: 'var(--thread-d)', bg: 'var(--vus-bg)' }
    : status === 'contacted' ? { fg: 'var(--benign)', bg: 'var(--benign-bg)' }
      : { fg: 'var(--faint)', bg: 'var(--paper-2)' };
  const noContact = !m.email && !m.phone;
  // a soft tint by role for visual hierarchy (carrier = faint red, at-risk = faint blue)
  const topTint = m.carrier ? 'var(--path)' : isProband ? 'var(--ink)' : 'var(--conflict)';
  return (
    <div style={{
      ...card, padding: 0, width: 210, overflow: 'hidden',
      border: isProband ? '1.5px solid var(--ink)' : '1px solid var(--line)',
    }}>
      <div style={{ height: 4, background: topTint }} />
      <div style={{ padding: '.65rem .75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '.4rem' }}>
          <span style={{ fontWeight: 700, fontSize: '.88rem' }}>{m.name}{m.deceased ? ' †' : ''}</span>
          <span style={mono({ fontSize: '.62rem', color: 'var(--faint)' })}>{m.relationship}</span>
        </div>
        <div style={{ marginTop: '.4rem', display: 'flex', gap: '.3rem', flexWrap: 'wrap' }}>
          {m.carrier ? <span style={tag('var(--path-d)', 'var(--path-bg)')}>carrier</span>
            : <span style={tag('var(--thread-d)', 'var(--vus-bg)')}>at-risk</span>}
          {!isProband && <span style={tag(sc.fg, sc.bg)}>{status}</span>}
        </div>
        <div style={{ marginTop: '.5rem', fontSize: '.72rem', color: 'var(--muted)', display: 'grid', gap: '.2rem' }}>
          {m.email
            ? <span style={{ display: 'flex', alignItems: 'center', gap: '.3rem' }}><Mail size={11} /> {m.email}</span>
            : <span style={{ display: 'flex', alignItems: 'center', gap: '.3rem', color: 'var(--path-d)' }}><AlertTriangle size={11} /> no email on file</span>}
          {m.phone && <span style={{ display: 'flex', alignItems: 'center', gap: '.3rem' }}><PhoneCall size={11} /> {m.phone}</span>}
        </div>
        {!isProband && !m.carrier && !drafted[m.id] && (
          <button onClick={() => setDrafted((d) => ({ ...d, [m.id]: true }))} disabled={noContact}
            style={{
              marginTop: '.55rem', width: '100%', fontSize: '.74rem', fontWeight: 600, borderRadius: 7, padding: '.38rem',
              background: noContact ? 'var(--paper-2)' : 'var(--thread)', color: noContact ? 'var(--faint)' : '#fff',
              cursor: noContact ? 'not-allowed' : 'pointer',
            }}>
            {noContact ? 'no contact route' : 'Draft recontact'}
          </button>
        )}
        {drafted[m.id] && (
          <div style={{ marginTop: '.55rem', fontSize: '.72rem', color: 'var(--benign)', display: 'flex', alignItems: 'center', gap: '.3rem' }}>
            <Check size={12} /> draft ready for clinician
          </div>
        )}
      </div>
    </div>
  );
}
