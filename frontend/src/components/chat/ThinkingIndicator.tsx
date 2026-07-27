export default function ThinkingIndicator({ statusText }: { statusText: string }) {
  return (
    <div className="msg-row tutor">
      <div className="tutor-avatar">AI</div>
      <div className="thinking-card">
        <span className="thinking-dots">
          <span />
          <span />
          <span />
        </span>
        {statusText}
      </div>
    </div>
  );
}
