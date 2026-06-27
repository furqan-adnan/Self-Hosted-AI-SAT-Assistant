import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import ASCIIText from './assets/components/ASCIIText';
import Ferrofluid from './assets/components/Ferrofluid/Ferrofluid';
import './App.css';

interface Message {
  sender: 'user' | 'tutor';
  text: string;
  isError?: boolean;
}

interface ParsedQuestion {
  section: string;
  domain: string;
  passage: string;
  question: string;
  options: { letter: string; text: string }[];
  answerLetter: string;
  explanation: string;
}

const SUGGESTIONS = [
  'Give me a Math question',
  'Give me a Reading & Writing question',
  "What's a good SAT score?",
];

function parseQuestionCard(raw: string): ParsedQuestion | null {
   
  const pattern =
    /\**Section:\**\s*(.*?)\s*\**Domain:\**\s*(.*?)\s*\**Passage(?:\/Context)?:\**\s*(.*?)\s*\**Question:\**\s*(.*?)\s*\**Options:\**\s*(.*?)\s*\**Answer:\**\s*(.*?)\s*\**Explanation:\**\s*([\s\S]*)/i;
  
  const match = raw.match(pattern);
  if (!match) return null;

  const [, section, domain, passage, question, optionsRaw, answerRaw, explanation] = match;

  const options: { letter: string; text: string }[] = [];
  const optionPattern = /\(([A-D])\)\s*([^()]+?)(?=\s*\([A-D]\)|$)/g;
  let optMatch: RegExpExecArray | null;
  while ((optMatch = optionPattern.exec(optionsRaw)) !== null) {
    options.push({ letter: optMatch[1], text: optMatch[2].trim() });
  }
  if (options.length < 2) return null;

  const answerLetterMatch = answerRaw.match(/([A-D])/);

  return {
    section: section.trim(),
    domain: domain.trim(),
    passage: passage.trim(),
    question: question.trim(),
    options,
    answerLetter: answerLetterMatch ? answerLetterMatch[1] : '',
    explanation: explanation.trim(),
  };
}

function QuestionCard({ data, showCursor }: { data: ParsedQuestion; showCursor: boolean }) {
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

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('Reading your message...');
  const [isStreaming, setIsStreaming] = useState(false);
  const [connection, setConnection] = useState<'connected' | 'busy' | 'offline'>('connected');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async (overrideText?: string) => {
    const userText = (overrideText ?? input).trim();
    if (!userText || loading || isStreaming) return;

    setInput('');
    
    // SHORT TERM MEMORY: Grab the last 4 successful messages before adding the new one
    const validHistory = messages.filter(m => !m.isError);
    const recentHistory = validHistory.slice(-2).map(m => ({
      role: m.sender === 'user' ? 'user' : 'model',
      content: m.text
    }));

    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setLoading(true);
    setConnection('busy');

    setStatusText('Reading your message...');
    const timers: ReturnType<typeof setTimeout>[] = [
      setTimeout(() => setStatusText('Thinking it through...'), 10000),
      setTimeout(() => setStatusText('Still working on it...'), 22000),
      setTimeout(() => setStatusText('Almost there...'), 32000),
    ];
    const clearAllTimers = () => timers.forEach(clearTimeout);

    try {
      const response = await fetch('https://fuqi11-sat-ai-backend.hf.space/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userText,
          history: recentHistory // Send the memory packet!
        }),
      });

      if (!response.ok) throw new Error('Backend server error');
      if (!response.body) throw new Error('No response body stream received');

      clearAllTimers();
      setLoading(false);
      setIsStreaming(true);

      setMessages((prev) => [...prev, { sender: 'tutor', text: '' }]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedResponse = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedResponse += chunk;

        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0) {
            updated[updated.length - 1] = { sender: 'tutor', text: accumulatedResponse };
          }
          return updated;
        });
      }

      setConnection('connected');
    } catch (error) {
      console.error(error);
      clearAllTimers();
      setConnection('offline');
      setMessages((prev) => [
        ...prev,
        {
          sender: 'tutor',
          isError: true,
          text: "Couldn't reach the tutor — the server may be waking up from idle. Send your message again in a few seconds.",
        },
      ]);
    } finally {
      clearAllTimers();
      setLoading(false);
      setIsStreaming(false);
    }
  };

  const isBusy = loading || isStreaming;

  return (
    <div className="sat-tutor-app">
      <div className="app-background">
        <Ferrofluid
          colors={["#3b82f6", "#1e40af", "#60a5fa"]}
          speed={0.4}
          scale={1.5}
          turbulence={0.8}
          fluidity={0.1}
          rimWidth={0.2}
          sharpness={3}
          glow={3}
          opacity={1}
          mouseInteraction={true}
        />
      </div>
      
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

      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="welcome">
            <div className="ascii-hero-wrapper">
              <ASCIIText
                text="SAT AI"
                enableWaves={true}
                asciiFontSize={8}
                textFontSize={150}
                textColor="#ffffff"
                planeBaseHeight={8}
              />
            </div>
            <h2>Ready when you are</h2>
            <p>Ask a math or reading question, or request a full practice problem.</p>
            <div className="chip-row">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
          const isLast = index === messages.length - 1;
          const showCursor = isStreaming && isLast;

          if (msg.sender === 'user') {
            return (
              <div className="msg-row user" key={index}>
                <div className="bubble user">
                  <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
                </div>
              </div>
            );
          }
            
          const parsed = !msg.isError ? parseQuestionCard(msg.text) : null;

          return (
            <div className="msg-row tutor" key={index}>
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
        })}

        {loading && (
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
        )}
      </div>

      <div className="input-bar">
        <div className="input-row">
          <input
            type="text"
            value={input}
            disabled={isBusy}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder={isBusy ? 'Please wait for the tutor to respond...' : 'Ask a question or request a practice problem...'}
          />
          <button className="send-btn" onClick={() => sendMessage()} disabled={isBusy} aria-label="Send message">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2 11 13" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M22 2 15 22l-4-9-9-4 20-7Z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;