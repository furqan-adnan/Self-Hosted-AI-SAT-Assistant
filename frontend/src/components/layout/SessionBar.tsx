export default function SessionBar({ connection }: { connection: 'connected' | 'busy' | 'offline' }) {
  return (
    <header className="session-bar">
      <div className="brand">
        <div className="brand-mark">SAT</div>
        <div className="brand-text">
          <h1>AI SAT Tutor</h1>
          <p>Digital SAT Practice &amp; Tutoring</p>
        </div>
      </div>
      <div className="status-pill">
        <span className={`status-dot ${connection}`} />
        {connection === 'busy' ? 'Generating' : connection === 'offline' ? 'Offline' : 'Connected'}
      </div>
    </header>
  );
}
