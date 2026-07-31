import { useState, useRef, useEffect } from 'react';
import type { Message } from '../types';
import { sendChatMessage } from '../services/api';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('Reading your message...');
  const [isStreaming, setIsStreaming] = useState(false);
  const [connection, setConnection] = useState<'connected' | 'busy' | 'offline'>('connected');
  const [modelProvider, setModelProvider] = useState<'local' | 'groq'>('local');
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
      const response = await sendChatMessage(userText, recentHistory, modelProvider);

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

  return {
    messages,
    input,
    setInput,
    loading,
    statusText,
    isStreaming,
    connection,
    isBusy,
    modelProvider,
    setModelProvider,
    sendMessage,
    scrollRef
  };
}
