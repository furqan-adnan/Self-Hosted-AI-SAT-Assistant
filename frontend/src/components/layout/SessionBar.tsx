interface SessionBarProps {
  connection: 'connected' | 'busy' | 'offline';
  modelProvider: 'local' | 'groq';
  setModelProvider: (provider: 'local' | 'groq') => void;
}

export default function SessionBar({ connection, modelProvider, setModelProvider }: SessionBarProps) {
  return (
    <header className="session-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div className="brand">
        <div className="brand-mark">SAT</div>
        <div className="brand-text">
          <h1>AI SAT Tutor</h1>
          <p>Digital SAT Practice &amp; Tutoring</p>
        </div>
      </div>
      
      <div className="controls" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <div className="model-selector" style={{ display: 'flex', background: 'rgba(255,255,255,0.1)', padding: '4px', borderRadius: '8px', fontSize: '13px' }}>
          <button 
            onClick={() => setModelProvider('local')}
            style={{ 
              padding: '6px 12px', 
              borderRadius: '6px', 
              border: 'none', 
              background: modelProvider === 'local' ? 'rgba(59, 130, 246, 0.8)' : 'transparent',
              color: 'white',
              cursor: 'pointer',
              fontWeight: modelProvider === 'local' ? 600 : 400
            }}
          >
            Gemma 9B (Local)
          </button>
          <button 
            onClick={() => setModelProvider('groq')}
            style={{ 
              padding: '6px 12px', 
              borderRadius: '6px', 
              border: 'none', 
              background: modelProvider === 'groq' ? 'rgba(59, 130, 246, 0.8)' : 'transparent',
              color: 'white',
              cursor: 'pointer',
              fontWeight: modelProvider === 'groq' ? 600 : 400
            }}
          >
            Groq Llama 3 (Fast)
          </button>
        </div>

        <div className="status-pill">
          <span className={`status-dot ${connection}`} />
          {connection === 'busy' ? 'Generating' : connection === 'offline' ? 'Offline' : 'Connected'}
        </div>
      </div>
    </header>
  );
}
