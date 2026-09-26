import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { getGraph, type Graph, type GraphNode, type CohortRow } from '../api';
import { card, mono, eyebrow, tag } from './ui';

const COLOR: Record<string, string> = {
  variant:   '#eaf0fb',
  gene:      '#c084fc',
  protein:   '#f472b6',
  source:    '#5b8cff',
  evidence:  '#67d4e5',
  criterion: '#fbbf24',
  warning:   '#f87171',
  verdict:   '#4ade80',
  carrier:   '#ff6b81',
  relative:  '#38bdf8',
};

const BASE_SIZE: Record<string, number> = {
  variant: 14, gene: 10, protein: 9, source: 10, evidence: 8, criterion: 8,
  warning: 8, verdict: 12, carrier: 9, relative: 8,
};

const GLOW: Record<string, number> = {
  variant: 24, verdict: 18, source: 14, gene: 12, protein: 10,
};

type FGNode = GraphNode & { x?: number; y?: number; __ring?: number };
type FGLink = { source: string | FGNode; target: string | FGNode; weight?: number; label?: string };

function nodeId(n: string | FGNode): string { return typeof n === 'object' ? n.id : n; }

export default function GraphView({ patientId, cohort, onPick }: { patientId: string; cohort?: CohortRow[] | null; onPick?: (r: CohortRow) => void }) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);

  useEffect(() => {
    setGraph(null); setErr(null); setSelected(null);
    getGraph(patientId).then(setGraph).catch((e) => setErr(String(e.message || e)));
  }, [patientId]);

  useEffect(() => {
    const el = wrapRef.current; if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el); setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [graph]);

  const data = useMemo(() => {
    if (!graph) return { nodes: [] as FGNode[], links: [] as FGLink[] };

    const byType: Record<string, GraphNode[]> = {};
    for (const n of graph.nodes) (byType[n.type] ||= []).push(n);

    const ringOrder = ['source', 'gene', 'protein', 'evidence', 'criterion', 'warning', 'verdict', 'carrier', 'relative'];
    const nodes: FGNode[] = [];
    for (const n of graph.nodes) {
      if (n.type === 'variant') {
        nodes.push({ ...n, x: 0, y: 0, __ring: 0 });
        continue;
      }
      const ringIdx = ringOrder.indexOf(n.type);
      const ring = ringIdx >= 0 ? ringIdx + 1 : 3;
      const sameType = byType[n.type] || [];
      const i = sameType.indexOf(n);
      const spread = sameType.length;
      const baseAngle = (ring * 0.7);
      const ang = baseAngle + (i / Math.max(1, spread)) * 2 * Math.PI;
      const radius = 120 + ring * 80;
      nodes.push({ ...n, x: Math.cos(ang) * radius, y: Math.sin(ang) * radius, __ring: ring });
    }
    return {
      nodes,
      links: graph.edges.map((e) => ({ source: e.source, target: e.target, weight: e.weight, label: e.label })),
    };
  }, [graph]);

  const neighbours = useMemo(() => {
    const m: Record<string, Set<string>> = {};
    data.links.forEach((l) => {
      const s = nodeId(l.source), t = nodeId(l.target);
      (m[s] ||= new Set()).add(t);
      (m[t] ||= new Set()).add(s);
    });
    return m;
  }, [data]);

  const lit = useCallback(
    (id: string) => !hover || hover === id || neighbours[hover]?.has(id),
    [hover, neighbours],
  );

  useEffect(() => {
    if (!graph) return;
    const id = setTimeout(() => {
      const fg = fgRef.current; if (!fg) return;
      try {
        fg.d3Force('charge').strength(-600).distanceMax(800);
        fg.d3Force('link').distance((l: any) => {
          const w = l.weight ?? 1;
          return 100 / Math.max(0.3, w);
        });
        fg.d3ReheatSimulation();
      } catch { /* forces not ready */ }
    }, 200);
    return () => clearTimeout(id);
  }, [graph]);

  const handleNodeClick = useCallback((node: any) => {
    const gn = graph?.nodes.find((n) => n.id === node.id);
    setSelected((prev) => prev?.id === node.id ? null : gn || null);
  }, [graph]);

  const handleBackgroundClick = useCallback(() => setSelected(null), []);

  if (err) return <div style={{ ...card, ...tag('var(--path-d)', 'var(--path-bg)'), whiteSpace: 'normal' }}>Error: {err}</div>;

  const panelOpen = selected !== null;

  return (
    <div style={{ ...card, padding: 0, overflow: 'hidden', background: '#0e1119', border: '1px solid #20263a', position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '.5rem', padding: '1rem 1.2rem .6rem' }}>
        <div>
          <div style={{ ...eyebrow, color: '#7f8aa3' }}>Evidence knowledge graph</div>
          {cohort && onPick && (
            <select
              value={patientId}
              onChange={(e) => { const row = cohort.find((c) => c.patient_id === e.target.value); if (row) onPick(row); }}
              style={{ marginTop: '.4rem', background: '#13161f', color: '#d7deec', border: '1px solid #2a3147', borderRadius: 8, padding: '.35rem .6rem', fontSize: '.82rem', fontWeight: 600, fontFamily: 'var(--sans)', cursor: 'pointer' }}>
              {cohort.map((c) => <option key={c.patient_id} value={c.patient_id}>{c.patient_name} — {c.gene} {c.hgvs_c}</option>)}
            </select>
          )}
          <div style={{ fontSize: '.78rem', color: '#9aa4b8', marginTop: '.35rem' }}>
            Click a node to inspect. Hover to trace connections. Drag to rearrange.
          </div>
        </div>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          {Object.entries(COLOR).map(([t, c]) => <Legend key={t} c={c} t={t} />)}
        </div>
      </div>

      <div style={{ display: 'flex', position: 'relative' }}>
        <div ref={wrapRef} style={{ flex: 1, height: 580, minWidth: 0, transition: 'flex .3s ease' }}>
          {graph && (
            <ForceGraph2D
              ref={fgRef}
              graphData={data}
              width={width}
              height={580}
              backgroundColor="#0e1119"
              cooldownTicks={250}
              d3VelocityDecay={0.25}
              onEngineStop={() => fgRef.current?.zoomToFit(500, 60)}
              onNodeHover={(n: any) => setHover(n ? n.id : null)}
              onNodeClick={handleNodeClick}
              onBackgroundClick={handleBackgroundClick}
              nodeRelSize={1}
              linkColor={(l: any) => {
                const s = nodeId(l.source), t = nodeId(l.target);
                const on = !hover || hover === s || hover === t;
                return on ? 'rgba(140,160,200,0.35)' : 'rgba(120,140,180,0.07)';
              }}
              linkWidth={(l: any) => {
                const s = nodeId(l.source), t = nodeId(l.target);
                const w = l.weight ?? 1;
                if (hover && (hover === s || hover === t)) return Math.max(2, w * 2);
                return Math.max(0.5, w * 0.8);
              }}
              nodePointerAreaPaint={(node: any, color, ctx) => {
                const baseR = BASE_SIZE[node.type] ?? 8;
                const s = node.size ?? 1;
                const hitR = baseR * s * 0.65 + 10;
                ctx.beginPath();
                ctx.arc(node.x, node.y, hitR, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={0.65}
              linkDirectionalArrowColor={(l: any) => {
                const s = nodeId(l.source), t = nodeId(l.target);
                const on = !hover || hover === s || hover === t;
                return on ? 'rgba(140,160,200,0.5)' : 'rgba(120,140,180,0.1)';
              }}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const baseR = BASE_SIZE[node.type] ?? 5;
                const sizeScale = node.size ?? 1;
                const r = baseR * sizeScale * 0.65;
                const color = COLOR[node.type] ?? '#8aa';
                const on = lit(node.id);
                const isSel = selected?.id === node.id;

                ctx.globalAlpha = on ? 1 : 0.15;

                const glowR = GLOW[node.type] ?? 8;
                ctx.shadowColor = color;
                ctx.shadowBlur = isSel ? glowR * 1.8 : glowR;

                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();
                ctx.shadowBlur = 0;

                if (isSel) {
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI);
                  ctx.strokeStyle = '#ffffff';
                  ctx.lineWidth = 1.5;
                  ctx.stroke();
                }

                if (node.type === 'variant') {
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, r + 5, 0, 2 * Math.PI);
                  ctx.strokeStyle = 'rgba(234,240,251,0.4)';
                  ctx.lineWidth = 1;
                  ctx.stroke();
                }

                if (node.type === 'verdict') {
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
                  ctx.strokeStyle = 'rgba(52,211,153,0.4)';
                  ctx.lineWidth = 1;
                  ctx.stroke();
                }

                if (node.type === 'warning') {
                  ctx.beginPath();
                  const s = r * 0.9;
                  ctx.moveTo(node.x, node.y - s - 1);
                  ctx.lineTo(node.x + s, node.y + s * 0.6);
                  ctx.lineTo(node.x - s, node.y + s * 0.6);
                  ctx.closePath();
                  ctx.fillStyle = color;
                  ctx.fill();
                }

                const fontSize = Math.max(2.5, (on && globalScale > 0.8 ? 10.5 : 9) / globalScale);
                ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = on ? '#d7deec' : 'rgba(150,160,180,0.2)';
                ctx.fillText(node.label, node.x, node.y + r + 3);

                if (on && node.meta && globalScale > 0.6) {
                  const metaSize = Math.max(2, 7.5 / globalScale);
                  ctx.font = `400 ${metaSize}px Inter, system-ui, sans-serif`;
                  ctx.fillStyle = 'rgba(180,190,210,0.6)';
                  ctx.fillText(node.meta, node.x, node.y + r + 3 + fontSize + 2);
                }

                ctx.globalAlpha = 1;
              }}
            />
          )}
          {!graph && <div style={{ color: '#7f8aa3', padding: '2rem', fontFamily: 'var(--mono)', fontSize: '.8rem' }}>building knowledge graph...</div>}
        </div>

        {panelOpen && selected && (
          <NodePanel node={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  );
}

function NodePanel({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const color = COLOR[node.type] ?? '#8aa';
  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0, zIndex: 5,
      width: 310, maxWidth: '85%', flexShrink: 0, background: 'rgba(19,22,31,0.97)', borderLeft: '1px solid #20263a',
      padding: '1rem', overflowY: 'auto', maxHeight: 580,
      animation: 'uvfade .25s ease both',
    }}>
      <style>{`@keyframes uvfade { from { opacity:0; transform: translateX(8px) } to { opacity:1; transform:none } }`}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginBottom: '.3rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` }} />
            <span style={{ ...mono({ fontSize: '.64rem', color: '#7f8aa3' }), textTransform: 'uppercase', letterSpacing: '.08em' }}>{node.type}</span>
          </div>
          <h3 style={{ fontSize: '1rem', color: '#e1e5ef', margin: 0, lineHeight: 1.3 }}>{node.label}</h3>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#7f8aa3', cursor: 'pointer',
          fontSize: '1.1rem', padding: '.2rem', lineHeight: 1,
        }}>x</button>
      </div>
      {node.meta && (
        <div style={{ ...mono({ fontSize: '.72rem' }), color: color, marginTop: '.4rem', padding: '.2rem .5rem', borderRadius: 5, background: `${color}15`, display: 'inline-block' }}>
          {node.meta}
        </div>
      )}
      {node.detail && (
        <p style={{ fontSize: '.82rem', color: '#b0b8cc', lineHeight: 1.6, marginTop: '.7rem' }}>
          {node.detail}
        </p>
      )}
      <div style={{ ...mono({ fontSize: '.6rem' }), color: '#5b647a', marginTop: '1rem', borderTop: '1px solid #20263a', paddingTop: '.5rem' }}>
        node: {node.id}
      </div>
    </div>
  );
}

function Legend({ c, t }: { c: string; t: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '.25rem', ...mono({ fontSize: '.6rem', color: '#7f8aa3' }) }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: c, boxShadow: `0 0 5px ${c}` }} /> {t}
    </span>
  );
}
