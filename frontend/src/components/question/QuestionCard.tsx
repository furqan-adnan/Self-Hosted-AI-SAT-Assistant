import { ParsedQuestion } from '../../types';

export default function QuestionCard({ data, showCursor }: { data: ParsedQuestion; showCursor: boolean }) {
  return (
    <div className="question-card">
      <div className="qc-tags">
        <span className="qc-tag">{data.section}</span>
        <span className="qc-tag domain">{data.domain}</span>
      </div>
      {data.passage && <p className="qc-passage">{data.passage}</p>}
      <p className="qc-question">{data.question}</p>
      <ul className="qc-options">
        {data.options.map((opt) => (
          <li
            key={opt.letter}
            className={`qc-option${opt.letter === data.answerLetter ? ' correct' : ''}`}
          >
            <span className="letter">({opt.letter})</span>
            <span>{opt.text}</span>
          </li>
        ))}
      </ul>
      {data.answerLetter && (
        <div className="qc-answer-row">
          <span>✓ Correct answer: {data.answerLetter}</span>
        </div>
      )}
      {data.explanation && (
        <p className="qc-explanation">
          {data.explanation}
          {showCursor && <span className="stream-cursor" />}
        </p>
      )}
    </div>
  );
}
