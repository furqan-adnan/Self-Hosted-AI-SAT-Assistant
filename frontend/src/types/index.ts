export interface Message {
  sender: 'user' | 'tutor';
  text: string;
  isError?: boolean;
}

export interface ParsedQuestion {
  section: string;
  domain: string;
  passage: string;
  question: string;
  options: { letter: string; text: string }[];
  answerLetter: string;
  explanation: string;
}

export interface ChatRequest {
  message: string;
  history: { role: string; content: string }[];
  model_provider?: 'local' | 'groq';
}
