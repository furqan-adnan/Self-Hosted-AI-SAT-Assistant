export default function InputBar({
  input,
  isBusy,
  onInputChange,
  onSend,
}: {
  input: string;
  isBusy: boolean;
  onInputChange: (val: string) => void;
  onSend: () => void;
}) {
  return (
    <div className="input-bar">
      <div className="input-row">
        <input
          type="text"
          value={input}
          disabled={isBusy}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
          placeholder={isBusy ? 'Please wait for the tutor to respond...' : 'Ask a question or request a practice problem...'}
        />
        <button className="send-btn" onClick={onSend} disabled={isBusy} aria-label="Send message">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 2 11 13" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M22 2 15 22l-4-9-9-4 20-7Z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
