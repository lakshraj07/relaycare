import { useEffect, useRef, useState, useCallback } from 'react';
import type { Structural } from '../api';

declare const $3Dmol: any;

function amColor(score: number): string {
  if (score >= 0.564) return '#d62728';
  if (score >= 0.34) return '#ff7f0e';
  return '#1f77b4';
}

function amColorHex(score: number): number {
  if (score >= 0.564) return 0xd62728;
  if (score >= 0.34) return 0xff7f0e;
  return 0x1f77b4;
}

const mono: React.CSSProperties = { fontFamily: 'var(--mono)' };

type ColorMode = 'am' | 'plddt' | 'neighbourhood';

interface Props {
  structural: Structural;
}

export default function StructureViewer({ structural }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const molDivRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ColorMode>('am');
  const [scriptLoaded, setScriptLoaded] = useState(typeof window !== 'undefined' && typeof (window as any).$3Dmol !== 'undefined');

  useEffect(() => {
    if (scriptLoaded) return;
    if (typeof (window as any).$3Dmol !== 'undefined') {
      setScriptLoaded(true);
      return;
    }
    const existing = document.querySelector('script[src*="3Dmol"]');
    if (existing) {
      existing.addEventListener('load', () => setScriptLoaded(true));
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://3dmol.org/build/3Dmol-min.js';
    script.onload = () => setScriptLoaded(true);
    script.onerror = () => setError('Failed to load 3Dmol.js');
    document.head.appendChild(script);
  }, [scriptLoaded]);

  useEffect(() => {
    if (!scriptLoaded || !wrapperRef.current) return;

    if (molDivRef.current) {
      molDivRef.current.remove();
      molDivRef.current = null;
    }
    viewerRef.current = null;

    const molDiv = document.createElement('div');
    molDiv.style.width = '100%';
    molDiv.style.height = '100%';
    molDiv.style.position = 'absolute';
    molDiv.style.top = '0';
    molDiv.style.left = '0';
    wrapperRef.current.appendChild(molDiv);
    molDivRef.current = molDiv;

    const viewer = $3Dmol.createViewer(molDiv, {
      backgroundColor: '#0d1117',
      antialias: true,
    });
    viewerRef.current = viewer;

    setLoading(true);
    setError(null);

    fetch(structural.structure_url)
      .then((r) => {
        if (!r.ok) throw new Error(`PDB fetch ${r.status}`);
        return r.text();
      })
      .then((pdb) => {
        if (viewerRef.current !== viewer) return;
        viewer.addModel(pdb, 'pdb');
        applyStyle(viewer, structural, mode);
        viewer.zoomTo();
        viewer.zoom(1.1);
        viewer.render();
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e.message || e));
        setLoading(false);
      });

    return () => {
      if (molDivRef.current) {
        molDivRef.current.remove();
        molDivRef.current = null;
      }
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structural.structure_url, scriptLoaded]);

  const changeMode = useCallback((m: ColorMode) => {
    setMode(m);
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.removeAllLabels();
    applyStyle(viewer, structural, m);
    viewer.render();
  }, [structural]);

  return (
    <div>
      <div style={{ display: 'flex', gap: '.4rem', marginBottom: '.5rem', flexWrap: 'wrap' }}>
        {(['am', 'plddt', 'neighbourhood'] as const).map((m) => (
          <button
            key={m}
            onClick={() => changeMode(m)}
            style={{
              ...mono,
              fontSize: '.68rem',
              fontWeight: mode === m ? 700 : 500,
              padding: '.25rem .55rem',
              borderRadius: 6,
              border: '1px solid var(--line)',
              background: mode === m ? 'var(--vus-bg)' : 'var(--surface)',
              color: mode === m ? 'var(--thread-d)' : 'var(--muted)',
              cursor: 'pointer',
            }}
          >
            {m === 'am' ? 'AlphaMissense' : m === 'plddt' ? 'pLDDT confidence' : 'neighbourhood'}
          </button>
        ))}
      </div>

      <div
        style={{
          width: '100%',
          height: 360,
          borderRadius: 10,
          overflow: 'hidden',
          border: '1px solid #20263a',
          position: 'relative',
          background: '#0d1117',
        }}
      >
        {/* 3Dmol mounts its own DOM here, outside React's tree */}
        <div ref={wrapperRef} style={{ position: 'absolute', inset: 0 }} />

        {/* Overlays are siblings, not children of the 3Dmol container */}
        {loading && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: '#0d1117', color: '#7f8aa3',
              ...mono, fontSize: '.8rem', zIndex: 10,
              pointerEvents: 'none',
            }}
          >
            Loading AlphaFold structure...
          </div>
        )}
        {error && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: '#0d1117', color: '#e8b06a',
              ...mono, fontSize: '.8rem', zIndex: 10,
            }}
          >
            {error}
          </div>
        )}
      </div>

      <div
        style={{
          display: 'flex', gap: '1rem', marginTop: '.5rem',
          alignItems: 'center', flexWrap: 'wrap',
        }}
      >
        <Legend mode={mode} />
        <div style={{ ...mono, fontSize: '.64rem', color: 'var(--faint)', marginLeft: 'auto' }}>
          drag to rotate, scroll to zoom, shift+drag to translate
        </div>
      </div>
    </div>
  );
}

function applyStyle(viewer: any, s: Structural, mode: ColorMode) {
  viewer.setStyle({}, { cartoon: { color: '#3a3f54' } });

  const heatmap = s.heatmap ?? [];

  if (mode === 'am') {
    for (const h of heatmap) {
      viewer.setStyle({ resi: h.residue }, { cartoon: { color: amColor(h.mean_am) } });
    }
  } else if (mode === 'plddt') {
    for (const h of heatmap) {
      const plddt = h.plddt ?? 50;
      let color: string;
      if (plddt >= 90) color = '#0053d6';
      else if (plddt >= 70) color = '#65cbf3';
      else if (plddt >= 50) color = '#ffdb13';
      else color = '#ff7d45';
      viewer.setStyle({ resi: h.residue }, { cartoon: { color } });
    }
  } else {
    for (const n of s.pathogenic_neighbours) {
      viewer.setStyle({ resi: n.residue }, { cartoon: { color: amColor(n.mean_am) } });
      viewer.addStyle(
        { resi: n.residue, atom: 'CA' },
        { sphere: { radius: 0.6, color: amColorHex(n.mean_am) } },
      );
    }
  }

  viewer.setStyle({ resi: s.residue }, { cartoon: { color: '#ffffff' } });
  viewer.addStyle({ resi: s.residue }, { stick: { radius: 0.2, color: 0xffffff } });
  viewer.addStyle(
    { resi: s.residue, atom: 'CA' },
    { sphere: { radius: 1.0, color: 0xff4444 } },
  );

  viewer.addLabel(`res ${s.residue}`, {
    position: { resi: s.residue, atom: 'CA' },
    backgroundColor: '#d62728',
    fontColor: 'white',
    fontSize: 11,
    borderRadius: 4,
    padding: 3,
  });
}

function Legend({ mode }: { mode: ColorMode }) {
  const items =
    mode === 'plddt'
      ? [
          { color: '#0053d6', label: 'Very high (>90)' },
          { color: '#65cbf3', label: 'High (70-90)' },
          { color: '#ffdb13', label: 'Low (50-70)' },
          { color: '#ff7d45', label: 'Very low (<50)' },
        ]
      : [
          { color: '#d62728', label: 'Pathogenic (>0.564)' },
          { color: '#ff7f0e', label: 'Ambiguous (0.34-0.564)' },
          { color: '#1f77b4', label: 'Benign (<0.34)' },
        ];

  return (
    <div style={{ display: 'flex', gap: '.6rem', flexWrap: 'wrap' }}>
      {items.map((it) => (
        <div key={it.label} style={{ display: 'flex', alignItems: 'center', gap: '.25rem' }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: it.color, display: 'inline-block' }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: '.62rem', color: 'var(--muted)' }}>{it.label}</span>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: '.25rem' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff4444', display: 'inline-block' }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: '.62rem', color: 'var(--muted)' }}>variant residue</span>
      </div>
    </div>
  );
}
