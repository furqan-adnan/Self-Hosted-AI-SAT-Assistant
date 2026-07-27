from typing import List, Dict, Generator, Any
from llama_cpp import Llama
from app.config import settings
from app.core.prompts import SAT_TUTOR_SYSTEM_PROMPT

llm = Llama(
    model_path=settings.MODEL_PATH,
    n_ctx=settings.LLM_CONTEXT_SIZE,      
    n_threads=settings.LLM_THREADS,     
    n_batch=settings.LLM_BATCH_SIZE      
)

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
    return llm(
        prompt=prompt,
        stream=True,
        max_tokens=max_tokens,        
        temperature=temperature,
        repeat_penalty=settings.REPEAT_PENALTY,
        stop=["<end_of_turn>", "</s>"]
    )

def generate_response_sync(prompt: str, max_tokens: int, temperature: float) -> str:
    response = llm(
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
