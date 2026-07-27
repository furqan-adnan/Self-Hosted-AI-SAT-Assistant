import re
import random
from typing import List

MATH_QUESTION_TRIGGER_PATTERN = re.compile(
    r'\b(give|generate|create|make|practice|quiz|test)\b.{0,40}'
    r'\b(math|algebra|equations?|percent(?:age)?|average|rate)\b',
    re.IGNORECASE
)
MATH_NOTES_EXCLUSION_PATTERN = re.compile(r'\b(notes?|guide|study material|my book)\b', re.IGNORECASE)

def should_use_programmatic_math(message: str) -> bool:
    if MATH_NOTES_EXCLUSION_PATTERN.search(message):
        return False
    return bool(MATH_QUESTION_TRIGGER_PATTERN.search(message))

def _generate_distractors(correct: int, count: int = 3) -> List[int]:
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
    total = start + per_correct * correct_count

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
    c = a * x_value + b

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

PERCENT_DIVISORS = {10: 10, 20: 5, 25: 4, 40: 5, 50: 2, 5: 20}

def generate_percentage_problem() -> str:
    percent = random.choice(list(PERCENT_DIVISORS.keys()))
    divisor = PERCENT_DIVISORS[percent]
    base = divisor * random.randint(2, 15)
    part = base * percent // 100

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

    values = [random.randint(60, 100) for _ in range(n - 1)]
    last = average * n - sum(values)
    attempts = 0
    while not (50 <= last <= 100) and attempts < 30:
        values = [random.randint(60, 100) for _ in range(n - 1)]
        last = average * n - sum(values)
        attempts += 1
    values.append(last)
    total = sum(values)

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
