import type { CSSProperties } from 'react';

export const card: CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 14,
  padding: '1.1rem 1.2rem', boxShadow: 'var(--sh-sm)',
};

export const mono = (s: CSSProperties = {}): CSSProperties => ({ fontFamily: 'var(--mono)', ...s });

export const tag = (fg: string, bg: string): CSSProperties => ({
  display: 'inline-block', fontFamily: 'var(--mono)', fontSize: '.68rem', fontWeight: 600,
  padding: '.14rem .5rem', borderRadius: 6, color: fg, background: bg, letterSpacing: '.04em',
});

export const eyebrow: CSSProperties = {
  fontFamily: 'var(--mono)', fontSize: '.66rem', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--faint)',
};

export function bandColor(band: string) {
  const b = (band || '').toLowerCase();
  if (b.includes('pathogenic')) return { fg: 'var(--path-d)', bg: 'var(--path-bg)' };
  if (b.includes('benign')) return { fg: 'var(--benign)', bg: 'var(--benign-bg)' };
  return { fg: 'var(--thread-d)', bg: 'var(--vus-bg)' };
}

export function yearsSince(date: string | null): number | null {
  if (!date) return null;
  const d = new Date(date);
  if (isNaN(d.getTime())) return null;
  return Math.max(0, Math.round((Date.now() - d.getTime()) / (365.25 * 864e5)));
}
