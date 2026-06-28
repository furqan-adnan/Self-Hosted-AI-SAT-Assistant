import os
import json
import re
import random
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
# SELF-CONSISTENCY CHECK FOR GENERATED MATH ANSWERS (LLM-generated path)
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

# Catches the "30x = 30x" failure mode - a word problem whose own numbers
# reduce to an equation that's true for every value of x. The model
# asserting a specific answer from a same-coefficient equation is invalid
# algebra, regardless of whether that asserted number happens to match
# one of the four options.
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

    # Degenerate-equation check runs first - if the underlying algebra is
    # broken, it doesn't matter whether the asserted number happens to
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


# -------------------------------------------------------------------------
# PROGRAMMATIC MATH QUESTION GENERATION (zero LLM cost, zero extra RAM)
# -------------------------------------------------------------------------
# For generic "give me a math question" style requests, we skip the LLM
# entirely and build the question in pure Python instead. Every template
# below is constructed ANSWER-FIRST: the correct value is picked before
# the problem's numbers are derived from it, which makes a degenerate or
# unsolvable equation structurally impossible - unlike asking an LLM to
# invent numbers and hoping they happen to work out.
#
# This only intercepts generic requests with no mention of the student's
# notes, so RAG-grounded requests ("...from my notes") still go through
# the existing BM25 + Gemma path untouched.

MATH_QUESTION_TRIGGER_PATTERN = re.compile(
    r'\b(give|generate|create|make|practice|quiz|test)\b.{0,40}'
    r'\b(math|algebra|equations?|percent(?:age)?|average|rate)\b',
    re.IGNORECASE
)
MATH_NOTES_EXCLUSION_PATTERN = re.compile(r'\b(notes?|guide|study material|my book)\b', re.IGNORECASE)


def should_use_programmatic_math(message: str) -> bool:
    if MATH_NOTES_EXCLUSION_PATTERN.search(message):
        return False  # let RAG + Gemma ground this in the student's own notes
    return bool(MATH_QUESTION_TRIGGER_PATTERN.search(message))


def _generate_distractors(correct: int, count: int = 3) -> List[int]:
    """Plausible-but-wrong nearby integers for multiple-choice distractors."""
    candidates = set()
    offsets = [-10, -5, -2, -1, 1, 2, 5, 10]
    random.shuffle(offsets)
    for off in offsets:
        val = correct + off
        if val != correct and val > 0:
            candidates.add(val)
        if len(candidates) >= count:
            break
    while len(candidates) < count:
        val = correct + random.randint(-15, 15)
        if val != correct and val > 0:
            candidates.add(val)
    return list(candidates)[:count]


def _build_options(correct_value: int, distractors: List[int]):
    values = [correct_value] + distractors
    random.shuffle(values)
    letters = ["A", "B", "C", "D"]
    options = list(zip(letters, values))
    correct_letter = next(l for l, v in options if v == correct_value)
    options_str = " ".join(f"({l}) {v}" for l, v in options)
    return options_str, correct_letter


def generate_rate_problem() -> str:
    start = random.choice([0, 5, 10, 12, 15, 20])
    per_correct = random.choice([3, 4, 5, 6, 7, 8, 9])
    correct_count = random.randint(4, 9)
    total = start + per_correct * correct_count  # guaranteed correct by construction

    options_str, correct_letter = _build_options(total, _generate_distractors(total))

    passage = (
        f"A group of friends are playing a game where each player starts with {start} points. "
        f"For every correct answer, a player earns {per_correct} points. If a player answers "
        f"{correct_count} questions correctly, how many points will they have at the end of the round?"
    )
    explanation = (
        f"Each correct answer earns {per_correct} points, so {correct_count} correct answers earn "
        f"{correct_count} * {per_correct} = {per_correct * correct_count} points. Adding the starting "
        f"{start} points gives {per_correct * correct_count} + {start} = {total} points."
    )

    return (
        f"**Section:** Math **Domain:** Problem Solving & Data Analysis\n"
        f"**Passage/Context:** {passage}\n"
        f"**Question:** What is the total number of points the player will have?\n"
        f"**Options:** {options_str}\n"
        f"**Answer:** ({correct_letter}) {total}\n"
        f"**Explanation:** {explanation}"
    )


def generate_linear_equation_problem() -> str:
    x_value = random.randint(2, 12)
    a = random.randint(2, 9)
    b = random.randint(1, 20)
    c = a * x_value + b  # guaranteed: (c - b) divides evenly by a

    distractors = [d for d in _generate_distractors(x_value) if d != x_value]
    while len(distractors) < 3:
        candidate = x_value + random.choice([-3, -2, -1, 1, 2, 3])
        if candidate > 0 and candidate not in distractors and candidate != x_value:
            distractors.append(candidate)

    options_str, correct_letter = _build_options(x_value, distractors[:3])

    explanation = (
        f"Subtract {b} from both sides: {a}x = {c - b}. Divide both sides by {a}: "
        f"x = {c - b} / {a} = {x_value}."
    )

    return (
        f"**Section:** Math **Domain:** Heart of Algebra\n"
        f"**Passage/Context:** Solve the equation for x: {a}x + {b} = {c}\n"
        f"**Question:** What is the value of x?\n"
        f"**Options:** {options_str}\n"
        f"**Answer:** ({correct_letter}) {x_value}\n"
        f"**Explanation:** {explanation}"
    )


# percent -> a small integer divisor such that base = divisor * k always
# divides evenly by percent/100, guaranteeing an exact integer answer.
PERCENT_DIVISORS = {10: 10, 20: 5, 25: 4, 40: 5, 50: 2, 5: 20}


def generate_percentage_problem() -> str:
    percent = random.choice(list(PERCENT_DIVISORS.keys()))
    divisor = PERCENT_DIVISORS[percent]
    base = divisor * random.randint(2, 15)       # guarantees clean division below
    part = base * percent // 100                  # exact, no rounding

    options_str, correct_letter = _build_options(part, _generate_distractors(part))

    passage = f"A store has {base} items in stock. {percent}% of the items are on sale."
    explanation = f"{percent}% of {base} is ({percent} / 100) * {base} = {part}."

    return (
        f"**Section:** Math **Domain:** Problem Solving & Data Analysis\n"
        f"**Passage/Context:** {passage}\n"
        f"**Question:** How many items are on sale?\n"
        f"**Options:** {options_str}\n"
        f"**Answer:** ({correct_letter}) {part}\n"
        f"**Explanation:** {explanation}"
    )


def generate_average_problem() -> str:
    n = random.randint(3, 5)
    average = random.randint(70, 92)

    # Derive the last score from the desired average, so total == average * n
    # exactly by construction - no rounding, no probabilistic correctness.
    values = [random.randint(60, 100) for _ in range(n - 1)]
    last = average * n - sum(values)
    attempts = 0
    while not (50 <= last <= 100) and attempts < 30:
        values = [random.randint(60, 100) for _ in range(n - 1)]
        last = average * n - sum(values)
        attempts += 1
    values.append(last)
    total = sum(values)  # always equals average * n, regardless of the loop above

    options_str, correct_letter = _build_options(average, _generate_distractors(average))

    values_str = ", ".join(str(v) for v in values[:-1]) + f", and {values[-1]}"
    explanation = (
        f"The average is the sum of the scores divided by the number of tests: "
        f"({' + '.join(str(v) for v in values)}) / {n} = {total} / {n} = {average}."
    )

    return (
        f"**Section:** Math **Domain:** Problem Solving & Data Analysis\n"
        f"**Passage/Context:** A student scored {values_str} on {n} tests.\n"
        f"**Question:** What is the student's average score across all tests?\n"
        f"**Options:** {options_str}\n"
        f"**Answer:** ({correct_letter}) {average}\n"
        f"**Explanation:** {explanation}"
    )


def generate_programmatic_math_question(message: str) -> str:
    msg_lower = message.lower()
    if any(k in msg_lower for k in ["percent", "percentage"]):
        return generate_percentage_problem()
    if any(k in msg_lower for k in ["average", "mean"]):
        return generate_average_problem()
    if any(k in msg_lower for k in ["algebra", "equation"]):
        return generate_linear_equation_problem()
    if "rate" in msg_lower:
        return generate_rate_problem()
    return random.choice([
        generate_rate_problem,
        generate_linear_equation_problem,
        generate_percentage_problem,
        generate_average_problem,
    ])()


@app.post("/api/chat")
async def chat_with_tutor(request: ChatRequest):
    def event_generator():
        try:
            # 0. Zero-cost programmatic math path - intercepts generic
            # "give me a math question" style requests before any BM25
            # lookup or LLM call happens. Guaranteed-correct by construction,
            # and strictly faster than the LLM path since it skips inference
            # entirely. Anything mentioning the student's notes, Reading
            # questions, or casual chat falls through to the code below,
            # completely unchanged.
            if should_use_programmatic_math(request.message):
                print(f"🧮 Programmatic math path triggered for: {request.message!r}", flush=True)
                question_text = generate_programmatic_math_question(request.message)
                for piece in chunk_text_for_pseudo_stream(question_text):
                    yield piece
                return

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