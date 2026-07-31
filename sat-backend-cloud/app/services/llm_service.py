from typing import List, Dict, Generator, Any, Optional
from llama_cpp import Llama
import os
try:
    from groq import Groq
except ImportError:
    Groq = None

from app.config import settings
from app.core.prompts import SAT_TUTOR_SYSTEM_PROMPT
from app.core.logger import logger

_llm: Optional[Llama] = None

def get_llm() -> Llama:
    """Load Gemma only when the local LLM path is used (avoids blocking Groq/template routes on cold start)."""
    global _llm
    if _llm is None:
        logger.info("Loading local Gemma model into memory...")
        _llm = Llama(
            model_path=settings.MODEL_PATH,
            n_ctx=settings.LLM_CONTEXT_SIZE,
            n_threads=settings.LLM_THREADS,
            n_batch=settings.LLM_BATCH_SIZE,
        )
    return _llm

groq_client = None
if Groq and settings.GROQ_API_KEY:
    groq_client = Groq(api_key=settings.GROQ_API_KEY)

def format_history(history: List[Dict[str, str]]) -> str:
    history_str = ""
    if history:
        history_str = "--- Recent Conversation Context ---\n"
        for msg in history:
            role = "Tutor" if msg.get("role") == "model" else "Student"
            content = msg.get("content", "")
            
            short_content = content[:settings.HISTORY_TRUNCATION_LENGTH] + "..." if len(content) > settings.HISTORY_TRUNCATION_LENGTH else content
            history_str += f"[{role}]: {short_content}\n"
        history_str += "-----------------------------------\n\n"
    return history_str

def build_prompt(message: str, history_str: str, context_str: str, is_relevant: bool) -> str:
    if is_relevant:
        prompt = (
            f"<start_of_turn>user\n"
            f"{SAT_TUTOR_SYSTEM_PROMPT}\n\n"
            f"Context from the student's verified SAT notes and study guides:\n"
            f"{context_str}\n\n"
            f"Instruction: Use the specific context formulas or facts above to build your question or response.\n\n"
            f"{history_str}"
            f"Student Question: {message}<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
    else:
        prompt = (
            f"<start_of_turn>user\n"
            f"{SAT_TUTOR_SYSTEM_PROMPT}\n\n"
            f"{history_str}"
            f"Student Question: {message}<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
    return prompt

def generate_response(prompt: str, max_tokens: int, temperature: float) -> Generator[Dict[str, Any], None, None]:
    return get_llm()(
        prompt=prompt,
        stream=True,
        max_tokens=max_tokens,        
        temperature=temperature,
        repeat_penalty=settings.REPEAT_PENALTY,
        stop=["<end_of_turn>", "</s>"]
    )

def generate_response_sync(prompt: str, max_tokens: int, temperature: float) -> str:
    response = get_llm()(
        prompt=prompt,
        stream=False,
        max_tokens=max_tokens,
        temperature=temperature,
        repeat_penalty=settings.REPEAT_PENALTY,
        stop=["<end_of_turn>", "</s>"]
    )
    if response.get("choices"):
        return response["choices"][0].get("text", "")
    return ""

def generate_groq_response(message: str, history: List[Dict[str, str]], context_str: str, is_relevant: bool) -> Generator[str, None, None]:
    if not groq_client:
        yield "Error: Groq API key is missing or invalid on the server."
        return

    messages = [
        {"role": "system", "content": SAT_TUTOR_SYSTEM_PROMPT}
    ]

    if is_relevant:
        messages.append({
            "role": "user", 
            "content": f"Context from the student's verified SAT notes and study guides:\n{context_str}\n\nInstruction: Use the specific context formulas or facts above to build your question or response."
        })

    for msg in history:
        role = "assistant" if msg.get("role") == "model" else "user"
        messages.append({"role": role, "content": msg.get("content", "")})
    
    messages.append({"role": "user", "content": message})

    stream = groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        stream=True,
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content
