import ReactMarkdown from 'react-markdown';
import QuestionCard from '../question/QuestionCard';
import { parseQuestionCard } from '../question/parseQuestion';
import type { Message } from '../../types';

export default function MessageRow({ msg, isStreaming, isLast }: { msg: Message; isStreaming: boolean; isLast: boolean }) {
  const showCursor = isStreaming && isLast;

  if (msg.sender === 'user') {
    return (
      <div className="msg-row user">
        <div className="bubble user">
          <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
        </div>
      </div>
    );
  }
    
  const parsed = !msg.isError ? parseQuestionCard(msg.text) : null;

  return (
    <div className="msg-row tutor">
      <div className="tutor-avatar">AI</div>
      <div className="tutor-content-node">
        {parsed ? (
          <QuestionCard data={parsed} showCursor={showCursor} />
        ) : (
          <div className={`bubble tutor${msg.isError ? ' error-card' : ''}`}>
            <div className="msg-prose">
              <ReactMarkdown>{msg.text}</ReactMarkdown>
              {showCursor && <span className="stream-cursor" />}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
