import { ParsedQuestion } from '../../types';

export function parseQuestionCard(raw: string): ParsedQuestion | null {
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
