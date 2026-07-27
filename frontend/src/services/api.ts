import { API_BASE_URL } from '../config/constants';
import { ChatRequest } from '../types';

export async function sendChatMessage(
  message: string,
  history: { role: string; content: string }[]
): Promise<Response> {
  const payload: ChatRequest = { message, history };
  
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  return response;
}
