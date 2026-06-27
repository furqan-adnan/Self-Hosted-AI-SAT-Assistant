import os
import json
import re
import difflib
import numpy as np
from typing import List, Dict, Optional, Tuple
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from llama_cpp import Llama
from rank_bm25 import BM25Okapi
from collections import Counter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "AI SAT Tutor Backend is awake and running!"}

# NEW: We now accept an optional 'history' array for memory
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

MODEL_PATH = "models/gemma-2-9b-it-Q4_K_M.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=3072,      
    n_threads=2,     
    n_batch=256      
)

# -------------------------------------------------------------------------
# REGEX TOKENIZER & CONVERSATIONAL STOPWORDS
# -------------------------------------------------------------------------
def regex_tokenize(text: str):
    return re.findall(r'\w+', text.lower())

BM25_STOPWORDS = {
    "explain", "from", "my", "notes", "give", "me", "a", "question", 
    "to", "solve", "hi", "hello", "hey", "test", "practice", "ask", 
    "want", "find", "show", "what", "is", "how", "do", "you", "can", "portion"
}

VALID_DOMAINS = ["trigonometry", "algebra", "equations", "maths", "math", "geometry", "shapes", "percent", "percentage", "statistics"]

# -------------------------------------------------------------------------
# ZERO-RAM BM25 KEYWORD INDEX INITIALIZATION & AUDIT
# -------------------------------------------------------------------------
corpus = []
bm25 = None
CORPUS_PATH = "cloud_corpus.json"

if os.path.exists(CORPUS_PATH):
    try:
        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            corpus = json.load(f)
        
        tokenized_corpus = [regex_tokenize(doc["text"]) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        print(f"✅ RAG Engine Active: Loaded {len(corpus)} full-page text nodes.", flush=True)
        
    except Exception as e:
        print(f"⚠️ Failed to compile RAG index: {e}", flush=True)
else:
    print("⚠️ 'cloud_corpus.json' not found. Operating in standard tutor mode.", flush=True)

SAT_TUTOR_SYSTEM_PROMPT = """You are an AI Digital SAT (DSAT) tutor.

Rule: when generating a practice question, NEVER write placeholders (e.g. "(passage will be provided)") or generic options (e.g. "A) inform... B) persuade..."). Always write a fully original, complete passage/problem, question, and 4 options.

Reading & Writing passages: 25-150 words, testing Words in Context, Text Structure/Purpose, Central Ideas, or Command of Evidence.
Math: cover Heart of Algebra, Problem Solving & Data Analysis, Advanced Math, or Geometry/Trig.
Generate exactly ONE question per turn unless asked for a full set.

Format for any generated question:
**Section:** ... **Domain:** ...
**Passage/Context:** ...
**Question:** ...
**Options:** (A) ... (B) ... (C) ... (D) ...
**Answer:** ...
**Explanation:** ...

For casual messages or general questions (not a request for a question), skip the format and reply directly in 1-3 sentences."""

# -------------------------------------------------------------------------
# SELF-CONSISTENCY CHECK FOR GENERATED MATH ANSWERS
# -------------------------------------------------------------------------
# Quantized 9B models occasionally compute the right number in the
# Explanation but then pick the wrong letter on the Answer line (or a
# number that doesn't match any of the four options at all). Since math
# questions have a checkable numeric answer, we verify the model's own
# explanation against its own options before the response ever reaches
# the student, instead of trusting the Answer line blindly.

QUESTION_SHAPE_PATTERN = re.compile(
    r'\*\*Options:\*\*\s*(.*?)\s*\*\*Answer:\*\*\s*(.*?)\s*\*\*Explanation:\*\*\s*([\s\S]*)',
    re.IGNORECASE
)
OPTION_PATTERN = re.compile(r'\(([A-D])\)\s*([^()]+?)(?=\s*\([A-D]\)|$)')
NUMBER_PATTERN = re.compile(r'[-+]?\d[\d,]*\.?\d*')

# NEW: catches the "30x = 30x" failure mode - a word problem whose own
# numbers reduce to an equation that's true for every value of x (or, with
# unequal coefficients, collapses to a trivial x=0). Either way, the model
# asserting a specific non-zero answer from a same-coefficient equation is
# invalid algebra, regardless of whether that asserted number happens to
# match one of the four options. This is a different failure than a wrong
# letter: the question's numbers themselves don't produce a unique answer.
DEGENERATE_EQUATION_PATTERN = re.compile(
    r'([-+]?\d*\.?\d*)\s*x\s*=\s*([-+]?\d*\.?\d*)\s*x\b',
    re.IGNORECASE
)


def _coef_to_float(raw: str) -> float:
    """Turns a coefficient string from the regex above into a float.
    Handles the implicit-1 cases regex naturally produces: '' -> 1, '-' -> -1, '+' -> 1."""
    if raw in ("", "+"):
        return 1.0
    if raw == "-":
        return -1.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def verify_math_answer(full_text: str) -> Tuple[str, str]:
    """
    Returns (text, status) where status is one of:
      'not_applicable' - couldn't parse a question shape, or options aren't
                          numeric (e.g. a Reading question) - nothing to check
      'consistent'      - the explanation's final computed number already
                          matches the declared Answer letter
      'fixed'           - the Answer letter was wrong; corrected it to match
                          the option the explanation's own math points to
      'unresolved'       - either the explanation's final computed number
                          matches NONE of the four options, OR the
                          explanation derives its answer from a degenerate
                          equation (same coefficient on both sides of "x")
                          that has no unique solution. Caller should
                          consider a retry.
    """
    match = QUESTION_SHAPE_PATTERN.search(full_text)
    if not match:
        return full_text, "not_applicable"

    options_raw, answer_raw, explanation = match.groups()

    option_values: Dict[str, str] = {}
    for letter, text in OPTION_PATTERN.findall(options_raw):
        num_match = NUMBER_PATTERN.search(text)
        if num_match:
            option_values[letter] = num_match.group().replace(",", "")

    if not option_values:
        return full_text, "not_applicable"  # non-numeric options - e.g. Reading

    declared_match = re.search(r'([A-D])', answer_raw)
    declared_letter = declared_match.group(1) if declared_match else None

    # NEW: degenerate-equation check runs first - if the underlying algebra
    # is broken, it doesn't matter whether the asserted number happens to
    # match an option; the question itself has no unique answer.
    for left_raw, right_raw in DEGENERATE_EQUATION_PATTERN.findall(explanation):
        left_val = _coef_to_float(left_raw)
        right_val = _coef_to_float(right_raw)
        if abs(left_val - right_val) < 1e-9:
            print(
                f"⚠️ Self-consistency check: explanation contains a degenerate equation "
                f"({left_raw or '1'}x = {right_raw or '1'}x) with no unique solution. "
                f"Flagging for retry.",
                flush=True
            )
            return full_text, "unresolved"

    # The model's own final computed number - the value after the LAST
    # "=" sign in its explanation (e.g. "...63 + 12 = 75 points" -> "75")
    computed_matches = re.findall(r'=\s*([-+]?\d[\d,]*\.?\d*)', explanation)
    if not computed_matches:
        return full_text, "not_applicable"  # no clear final computation to check

    computed_value = computed_matches[-1].replace(",", "")
    matching_letters = [l for l, v in option_values.items() if v == computed_value]

    if declared_letter and computed_value == option_values.get(declared_letter):
        return full_text, "consistent"

    if len(matching_letters) == 1:
        corrected_letter = matching_letters[0]
        print(
            f"⚠️ Self-consistency fix: Answer said {declared_letter} but the explanation "
            f"computes {computed_value}, matching option {corrected_letter}. Correcting.",
            flush=True
        )
        fixed_answer_raw = re.sub(r'[A-D]', corrected_letter, answer_raw, count=1)
        fixed_text = full_text[:match.start(2)] + fixed_answer_raw + full_text[match.end(2):]
        return fixed_text, "fixed"

    print(
        f"⚠️ Self-consistency check: explanation computes {computed_value}, which matches "
        f"NONE of the four options {option_values}. Flagging for retry.",
        flush=True
    )
    return full_text, "unresolved"


def chunk_text_for_pseudo_stream(text: str, chunk_size: int = 24):
    """Splits a fully-buffered response into pieces so the frontend's
    streaming/cursor animation still has something to render, even though
    the verification step required waiting for the full response first."""
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


@app.post("/api/chat")
async def chat_with_tutor(request: ChatRequest):
    def event_generator():
        try:
            context_str = ""
            is_relevant = False
            
            # --- PROCESS SHORT TERM MEMORY TRANSCRIPT ---
            history_str = ""
            if request.history:
                history_str = "--- Recent Conversation Context ---\n"
                for msg in request.history:
                    role = "Tutor" if msg.get("role") == "model" else "Student"
                    content = msg.get("content", "")
                    
                    short_content = content[:80] + "..." if len(content) > 80 else content
                    history_str += f"[{role}]: {short_content}\n"
                history_str += "-----------------------------------\n\n"
            
            # 1. Advanced BM25 Keyword Search & Expansion
            if bm25 is not None and len(corpus) > 0:
                raw_tokens = regex_tokenize(request.message)
                filtered_tokens = [t for t in raw_tokens if t not in BM25_STOPWORDS]
                
                if len(filtered_tokens) > 0:
                    expanded_query = []
                    for t in filtered_tokens:
                        expanded_query.append(t)
                        
                        closest_matches = difflib.get_close_matches(t, VALID_DOMAINS, n=1, cutoff=0.7)
                        corrected_t = closest_matches[0] if closest_matches else t
                        
                        if corrected_t in ["trigonometry"]:
                            expanded_query.extend(["sin", "cos", "tan", "theta", "triangle", "sohcahtoa", "radians"])
                        elif corrected_t in ["algebra", "equations", "maths", "math"]:
                            expanded_query.extend(["linear", "quadratic", "system", "intercept", "slope", "xy", "equation"])
                        elif corrected_t in ["geometry", "shapes"]:
                            expanded_query.extend(["circle", "area", "volume", "radius", "arc", "angle", "theorem"])
                        elif corrected_t in ["percent", "percentage", "statistics"]:
                            expanded_query.extend(["mean", "median", "margin", "deviation", "ratio", "proportion"])
                    
                    scores = np.array(bm25.get_scores(expanded_query))
                    
                    if np.max(scores) == 0.0 and len(expanded_query) > 0:
                        fallback_scores = np.zeros(len(corpus))
                        for idx, doc in enumerate(corpus):
                            doc_text_lower = doc["text"].lower()
                            match_count = sum(1 for token in expanded_query if re.search(rf'\b{re.escape(token)}\b', doc_text_lower))
                            fallback_scores[idx] = float(match_count)
                        scores = fallback_scores

                    top_indices = np.argsort(scores)[::-1][:1]
                    context_segments = []
                    
                    for idx in top_indices:
                        if scores[idx] > 0.0:  
                            is_relevant = True
                            matched_page = corpus[idx]
                            
                            truncated_text = matched_page['text'][:250]
                            if len(matched_page['text']) > 250:
                                truncated_text += "..."
                                
                            context_segments.append(
                                f"--- Reference Material [{matched_page['source']}] ---\n"
                                f"{truncated_text}"
                            )
                    
                    if is_relevant:
                        context_str = "\n\n".join(context_segments)

            # 2. Manual Custom Token Compilation (with history injected safely)
            if is_relevant:
                prompt = (
                    f"<start_of_turn>user\n"
                    f"{SAT_TUTOR_SYSTEM_PROMPT}\n\n"
                    f"Context from the student's verified SAT notes and study guides:\n"
                    f"{context_str}\n\n"
                    f"Instruction: Use the specific context formulas or facts above to build your question or response.\n\n"
                    f"{history_str}"
                    f"Student Question: {request.message}<end_of_turn>\n"
                    f"<start_of_turn>model\n"
                )
            else:
                prompt = (
                    f"<start_of_turn>user\n"
                    f"{SAT_TUTOR_SYSTEM_PROMPT}\n\n"
                    f"{history_str}"
                    f"Student Question: {request.message}<end_of_turn>\n"
                    f"<start_of_turn>model\n"
                )

            # 3. Native Low-Overhead Text String Completion Generation
            #
            # Casual replies and Reading/Writing questions still stream live,
            # token by token, exactly as before. Only Math questions get
            # buffered for a self-consistency check, since they're the only
            # case with a checkable numeric answer. The first ~120 characters
            # decide which path a response takes:
            #   - doesn't start with "**" at all          -> casual, passthrough immediately
            #   - "**Section:** Math" appears in that window -> buffer + verify
            #   - anything else (e.g. Reading and Writing)  -> passthrough, flush buffer
            response = llm(
                prompt=prompt,
                stream=True,
                max_tokens=256,        
                temperature=0.85,      # HIGHER TEMPERATURE = MUCH MORE VARIETY IN QUESTIONS! 
                repeat_penalty=1.1,
                stop=["<end_of_turn>", "</s>"]
            )

            full_text = ""
            mode = "undetermined"  # 'undetermined' -> 'passthrough' or 'buffered'
            DETECTION_WINDOW = 120

            for chunk in response:
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    text_piece = chunk["choices"][0]["text"]
                    if not text_piece:
                        continue
                    full_text += text_piece

                    if mode == "undetermined":
                        looks_like_schema = full_text.lstrip().startswith("**")
                        if not looks_like_schema:
                            # Casual reply - won't be a question card at all, stream live
                            mode = "passthrough"
                            yield full_text
                        elif len(full_text) >= DETECTION_WINDOW:
                            if re.search(r'\*\*Section:\*\*\s*Math\b', full_text, re.IGNORECASE):
                                mode = "buffered"  # hold everything - verify before sending
                            else:
                                mode = "passthrough"  # e.g. Reading and Writing - stream live
                                yield full_text
                        # else: still deciding, keep accumulating silently
                    elif mode == "passthrough":
                        yield text_piece
                    # mode == "buffered": intentionally yield nothing yet

            if mode == "undetermined":
                # Stream ended before we ever resolved (very short reply) - flush as-is
                yield full_text

            elif mode == "buffered":
                full_text, status = verify_math_answer(full_text)

                if status == "unresolved":
                    print("🔁 Retrying math question generation once due to self-consistency mismatch...", flush=True)
                    retry_prompt = prompt + (
                        "Important: in your previous attempt, either your final computed answer "
                        "did not match any of the four listed options, or the equation you set up "
                        "reduced to the same expression on both sides (no unique solution). Choose "
                        "numbers that produce a clean equation with exactly one solution, recompute "
                        "carefully, and make sure the Answer line exactly matches one of (A)-(D).\n"
                    )
                    try:
                        retry_response = llm(
                            prompt=retry_prompt,
                            max_tokens=256,
                            temperature=0.5,   # lower than the main call - retry favors correctness over variety
                            repeat_penalty=1.1,
                            stop=["<end_of_turn>", "</s>"]
                        )
                        retry_text = ""
                        if retry_response.get("choices"):
                            retry_text = retry_response["choices"][0].get("text", "")

                        if retry_text.strip():
                            retry_fixed_text, retry_status = verify_math_answer(retry_text)
                            if retry_status in ("consistent", "fixed"):
                                full_text, status = retry_fixed_text, retry_status
                            # else: retry didn't help either - fall back to the original attempt
                    except Exception as retry_error:
                        print(f"⚠️ Retry generation failed: {retry_error}", flush=True)
                        # fall back to the original (unresolved) attempt below

                for piece in chunk_text_for_pseudo_stream(full_text):
                    yield piece

        except Exception as e:
            yield f"Error encountered: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")