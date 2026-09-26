import { Link, useLocation } from 'react-router-dom';

export default function Navigation() {
  const { pathname } = useLocation();
  const link = (to: string, label: string) => (
    <Link
      to={to}
      style={{
        fontWeight: 600,
        fontSize: '.95rem',
        color: pathname === to ? 'var(--thread-d)' : 'var(--muted)',
        paddingBottom: '2px',
        borderBottom: pathname === to ? '2px solid var(--thread)' : '2px solid transparent',
      }}
    >
      {label}
    </Link>
  );

  return (
    <nav style={{ position: 'sticky', top: 0, zIndex: 100 }}>
      <div style={{ background: 'rgba(255,255,255,.82)', backdropFilter: 'blur(10px)', borderBottom: '1px solid var(--line)' }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.85rem 2rem' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '.7rem' }} aria-label="RelayCare home">
            <img src="/relaycare-mark.png" alt="" aria-hidden="true" style={{ height: '42px', width: '42px', objectFit: 'contain', display: 'block' }} />
            <span className="display" style={{ fontSize: '1.45rem', color: 'var(--ink)', letterSpacing: '-.03em' }}>RelayCare</span>
          </Link>

          <div style={{ display: 'flex', gap: '1.9rem', alignItems: 'center' }}>
            <span className="hide-sm">{link('/', 'Home')}</span>
            <span className="hide-sm">{link('/mission', 'Mission')}</span>
            <span className="hide-sm">{link('/technology', 'Technology')}</span>
            <Link to="/app" className="btn btn-primary btn-sm">Open Dashboard</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
