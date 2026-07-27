import re
from typing import Tuple, Dict
from app.config import settings
from app.core.logger import logger

QUESTION_SHAPE_PATTERN = re.compile(
    r'\*\*Options:\*\*\s*(.*?)\s*\*\*Answer:\*\*\s*(.*?)\s*\*\*Explanation:\*\*\s*([\s\S]*)',
    re.IGNORECASE
)
OPTION_PATTERN = re.compile(r'\(([A-D])\)\s*([^()]+?)(?=\s*\([A-D]\)|$)')
NUMBER_PATTERN = re.compile(r'[-+]?\d[\d,]*\.?\d*')

DEGENERATE_EQUATION_PATTERN = re.compile(
    r'([-+]?\d*\.?\d*)\s*x\s*=\s*([-+]?\d*\.?\d*)\s*x\b',
    re.IGNORECASE
)

def _coef_to_float(raw: str) -> float:
    if raw in ("", "+"):
        return 1.0
    if raw == "-":
        return -1.0
    try:
        return float(raw)
    except ValueError:
        return 0.0

def verify_math_answer(full_text: str) -> Tuple[str, str]:
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
        return full_text, "not_applicable"

    declared_match = re.search(r'([A-D])', answer_raw)
    declared_letter = declared_match.group(1) if declared_match else None

    for left_raw, right_raw in DEGENERATE_EQUATION_PATTERN.findall(explanation):
        left_val = _coef_to_float(left_raw)
        right_val = _coef_to_float(right_raw)
        if abs(left_val - right_val) < 1e-9:
            logger.warning(
                f"Self-consistency check: explanation contains a degenerate equation "
                f"({left_raw or '1'}x = {right_raw or '1'}x) with no unique solution. "
                f"Flagging for retry."
            )
            return full_text, "unresolved"

    computed_matches = re.findall(r'=\s*([-+]?\d[\d,]*\.?\d*)', explanation)
    if not computed_matches:
        return full_text, "not_applicable"

    computed_value = computed_matches[-1].replace(",", "")
    matching_letters = [l for l, v in option_values.items() if v == computed_value]

    if declared_letter and computed_value == option_values.get(declared_letter):
        return full_text, "consistent"

    if len(matching_letters) == 1:
        corrected_letter = matching_letters[0]
        logger.warning(
            f"Self-consistency fix: Answer said {declared_letter} but the explanation "
            f"computes {computed_value}, matching option {corrected_letter}. Correcting."
        )
        fixed_answer_raw = re.sub(r'[A-D]', corrected_letter, answer_raw, count=1)
        fixed_text = full_text[:match.start(2)] + fixed_answer_raw + full_text[match.end(2):]
        return fixed_text, "fixed"

    logger.warning(
        f"Self-consistency check: explanation computes {computed_value}, which matches "
        f"NONE of the four options {option_values}. Flagging for retry."
    )
    return full_text, "unresolved"

def chunk_text_for_pseudo_stream(text: str, chunk_size: int = None):
    if chunk_size is None:
        chunk_size = settings.STREAM_CHUNK_SIZE
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]
