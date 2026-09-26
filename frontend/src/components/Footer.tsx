import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container" style={{ padding: '2.5rem 2rem', display: 'flex', flexWrap: 'wrap', gap: '1.5rem', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ maxWidth: '380px' }}>
          <img src="/logo-footer.png" alt="RelayCare" style={{ height: '60px', width: 'auto' }} />
          <div style={{ fontSize: '.85rem', color: 'var(--muted)', marginTop: '.55rem' }}>
            Closing the diagnostic loop that stays open for years, for the patient and their family.
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1.5rem', fontSize: '.9rem', color: 'var(--muted)', fontWeight: 600, flexWrap: 'wrap' }}>
          <Link to="/mission">Mission</Link>
          <Link to="/technology">Technology</Link>
          <Link to="/app">Simulator</Link>
        </div>
        <div style={{ fontSize: '.8rem', color: 'var(--faint)' }}>
          Gemini 3.1 · Google ADK (Agent Builder) · Fivetran MCP · FHIR R4 · draft-only, human-in-the-loop
        </div>
      </div>
    </footer>
  );
}
