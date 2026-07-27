import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.config import settings
from app.core.logger import logger
from app.services.math_generator import should_use_programmatic_math, generate_programmatic_math_question
from app.services.answer_verifier import chunk_text_for_pseudo_stream, verify_math_answer
from app.services.rag_service import retrieve_context
from app.services.llm_service import format_history, build_prompt, generate_response, generate_response_sync

router = APIRouter()

@router.post("/api/chat")
async def chat_with_tutor(request: ChatRequest):
    def event_generator():
        try:
            if should_use_programmatic_math(request.message):
                logger.info(f"Programmatic math path triggered for: {request.message!r}")
                question_text = generate_programmatic_math_question(request.message)
                for piece in chunk_text_for_pseudo_stream(question_text):
                    yield piece
                return

            history_str = format_history(request.history)
            context_str, is_relevant = retrieve_context(request.message)
            prompt = build_prompt(request.message, history_str, context_str, is_relevant)

            response = generate_response(
                prompt=prompt,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )

            full_text = ""
            mode = "undetermined"

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
                        elif len(full_text) >= settings.DETECTION_WINDOW:
                            if re.search(r'\*\*Section:\*\*\s*Math\b', full_text, re.IGNORECASE):
                                mode = "buffered"
                            else:
                                mode = "passthrough"
                                yield full_text
                    elif mode == "passthrough":
                        yield text_piece

            if mode == "undetermined":
                yield full_text

            elif mode == "buffered":
                full_text, status = verify_math_answer(full_text)

                if status == "unresolved":
                    logger.warning("Retrying math question generation once due to self-consistency mismatch...")
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

        except Exception as e:
            logger.error(f"Error in chat stream: {str(e)}")
            yield f"Error encountered: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")

    return StreamingResponse(event_generator(), media_type="text/plain")
