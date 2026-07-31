import re
import time
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.config import settings
from app.core.logger import logger
from app.services.math_generator import should_use_programmatic_math, generate_programmatic_math_question
from app.services.reading_generator import should_use_programmatic_reading, generate_programmatic_reading_question
from app.services.answer_verifier import chunk_text_for_pseudo_stream, verify_math_answer
from app.services.rag_service import retrieve_context
from app.services.llm_service import format_history, build_prompt, generate_response, generate_response_sync, generate_groq_response

router = APIRouter()
llm_lock = threading.Lock()

# Pattern to detect if user is asking for a practice question (not about their notes)
QUESTION_REQUEST_PATTERN = re.compile(
    r'\b(give|generate|create|make|practice|quiz|test|try|want|need|show|get)\b.{0,50}'
    r'\b(question|problem|practice|quiz|test)\b',
    re.IGNORECASE
)


def _should_skip_rag(message: str) -> bool:
    """Skip RAG injection when user is asking for a generated question, not about their notes."""
    if QUESTION_REQUEST_PATTERN.search(message):
        return True
    return False


@router.post("/api/chat")
async def chat_with_tutor(request: ChatRequest):
    def event_generator():
        try:
            # 0. Groq API Route (Fast, high-accuracy, 3rd party LLM)
            if request.model_provider == "groq":
                logger.info("Routing request to Groq API...")
                if _should_skip_rag(request.message):
                    context_str, is_relevant = "", False
                else:
                    context_str, is_relevant = retrieve_context(request.message)
                
                for chunk in generate_groq_response(request.message, request.history, context_str, is_relevant):
                    yield chunk
                return

            # 1. Programmatic Math Route (instant, no LLM)
            if should_use_programmatic_math(request.message):
                logger.info(f"Programmatic math path triggered for: {request.message!r}")
                question_text = generate_programmatic_math_question(request.message)
                for piece in chunk_text_for_pseudo_stream(question_text):
                    yield piece
                return

            # 2. Programmatic Reading & Writing Route (instant, no LLM)
            if should_use_programmatic_reading(request.message):
                logger.info(f"Programmatic R&W path triggered for: {request.message!r}")
                question_text = generate_programmatic_reading_question(request.message)
                for piece in chunk_text_for_pseudo_stream(question_text):
                    yield piece
                return

            # 3. LLM Generation Route (Requires Queue)
            acquired = llm_lock.acquire(blocking=False)
            if not acquired:
                yield "[System]: The AI Tutor is currently helping another student. You are in the queue...\n\n"
                llm_lock.acquire(blocking=True)

            try:
                history_str = format_history(request.history)

                # Skip RAG when user is asking for a practice question — saves ~60 tokens
                if _should_skip_rag(request.message):
                    context_str, is_relevant = "", False
                    logger.info("Skipped RAG: user is requesting a generated question.")
                else:
                    context_str, is_relevant = retrieve_context(request.message)

                prompt = build_prompt(request.message, history_str, context_str, is_relevant)

                response = generate_response(
                    prompt=prompt,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE
                )

                full_text = ""
                mode = "undetermined"
                last_yield_time = time.time()

                for chunk in response:
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        text_piece = chunk["choices"][0]["text"]
                        if not text_piece:
                            continue
                        full_text += text_piece

                        if mode == "undetermined":
                            looks_like_schema = full_text.lstrip().startswith("**")
                            if not looks_like_schema:
                                mode = "passthrough"
                                yield full_text
                                last_yield_time = time.time()
                            elif len(full_text) >= settings.DETECTION_WINDOW:
                                if re.search(r'\*\*Section:\*\*\s*Math\b', full_text, re.IGNORECASE):
                                    mode = "buffered"
                                else:
                                    mode = "passthrough"
                                    yield full_text
                                    last_yield_time = time.time()
                        elif mode == "passthrough":
                            yield text_piece
                            last_yield_time = time.time()

                    # Heartbeat: keep HTTP connection alive during buffered/undetermined mode
                    if mode in ("buffered", "undetermined") and (time.time() - last_yield_time) > 15:
                        yield " "
                        last_yield_time = time.time()

                if mode == "undetermined":
                    yield full_text

                elif mode == "buffered":
                    full_text, status = verify_math_answer(full_text)

                    if status == "unresolved":
                        logger.warning("Retrying math question generation once due to self-consistency mismatch...")
                        yield " "  # keep-alive before retry
                        retry_prompt = prompt + (
                            "Important: in your previous attempt, either your final computed answer "
                            "did not match any of the four listed options, or the equation you set up "
                            "reduced to the same expression on both sides (no unique solution). Choose "
                            "numbers that produce a clean equation with exactly one solution, recompute "
                            "carefully, and make sure the Answer line exactly matches one of (A)-(D).\n"
                        )
                        try:
                            retry_text = generate_response_sync(
                                prompt=retry_prompt,
                                max_tokens=settings.MAX_TOKENS,
                                temperature=settings.RETRY_TEMPERATURE
                            )

                            if retry_text.strip():
                                retry_fixed_text, retry_status = verify_math_answer(retry_text)
                                if retry_status in ("consistent", "fixed"):
                                    full_text, status = retry_fixed_text, retry_status
                        except Exception as retry_error:
                            logger.error(f"Retry generation failed: {retry_error}")

                    for piece in chunk_text_for_pseudo_stream(full_text):
                        yield piece
            finally:
                llm_lock.release()

        except Exception as e:
            logger.error(f"Error in chat stream: {str(e)}")
            yield f"Error encountered: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")
