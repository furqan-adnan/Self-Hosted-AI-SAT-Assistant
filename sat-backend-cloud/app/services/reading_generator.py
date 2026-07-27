import random
import re
from typing import Tuple

READING_QUESTION_TRIGGER_PATTERN = re.compile(
    r'(?:'
    r'\b(give|generate|create|make|practice|quiz|test|try|want|need|show|get|help|do|start)\b.{0,50}'
    r'\b(reading|writing|grammar|vocabulary|english|vocab|verbal|r&w|rw|language|sentence|passage)\b'
    r'|'
    r'\b(reading|writing|grammar|vocabulary|english|vocab|verbal|r&w|rw|language|sentence|passage)\b.{0,50}'
    r'\b(question|problem|practice|quiz|test)\b'
    r')',
    re.IGNORECASE
)
READING_NOTES_EXCLUSION_PATTERN = re.compile(r'\b(notes?|guide|study material|my book)\b', re.IGNORECASE)

def should_use_programmatic_reading(message: str) -> bool:
    if READING_NOTES_EXCLUSION_PATTERN.search(message):
        return False
    return bool(READING_QUESTION_TRIGGER_PATTERN.search(message))

def generate_grammar_subject_verb() -> str:
    templates = [
        {
            "passage": "The collection of rare books, which includes several first editions from the 19th century, ______ on display at the main library.",
            "correct": "is",
            "distractors": ["are", "were", "have been"],
            "explanation": "The subject of the sentence is 'collection' (singular). The phrase 'which includes several first editions from the 19th century' is a non-restrictive clause modifying the subject, but it does not change the subject's number. Therefore, the singular verb 'is' is required."
        },
        {
            "passage": "Despite the harsh weather conditions, neither the researchers nor the lead scientist ______ to abandon the expedition.",
            "correct": "wants",
            "distractors": ["want", "are wanting", "have wanted"],
            "explanation": "When using 'neither... nor', the verb must agree with the subject closest to it. The closest subject is 'the lead scientist', which is singular. Therefore, the singular verb 'wants' is correct."
        },
        {
            "passage": "A basket of fresh apples, along with several jars of homemade jam, ______ delivered to the neighbors this morning.",
            "correct": "was",
            "distractors": ["were", "are", "have been"],
            "explanation": "The subject is 'basket' (singular). Phrases beginning with 'along with', 'as well as', or 'in addition to' do not make the subject plural. Therefore, the singular verb 'was' is required."
        }
    ]
    return _format_question(random.choice(templates), "Grammar: Subject-Verb Agreement")

def generate_grammar_transition() -> str:
    templates = [
        {
            "passage": "Many urban planners advocate for increasing green spaces in cities to reduce the urban heat island effect. ______, these parks provide essential habitats for local wildlife.",
            "correct": "Furthermore",
            "distractors": ["However", "Consequently", "Nevertheless"],
            "explanation": "The second sentence adds another supporting point (providing habitats) to the first sentence's positive point (reducing heat). 'Furthermore' correctly signals the addition of a related, supporting idea."
        },
        {
            "passage": "The startup's new software platform was highly praised by tech critics for its innovative interface. ______, it struggled to attract a broad user base due to its steep learning curve.",
            "correct": "Nevertheless",
            "distractors": ["Therefore", "Moreover", "In addition"],
            "explanation": "The first sentence presents a positive outcome (praise from critics), while the second presents a negative one (struggling to attract users). 'Nevertheless' correctly signals a contrast or unexpected shift."
        },
        {
            "passage": "The soil in the region lacks essential nutrients for agriculture. ______, the local government has subsidized the cost of high-quality fertilizers for farmers.",
            "correct": "Consequently",
            "distractors": ["Similarly", "Instead", "Meanwhile"],
            "explanation": "The lack of nutrients is the cause, and the government subsidizing fertilizer is the effect or result. 'Consequently' correctly signals a cause-and-effect relationship."
        }
    ]
    return _format_question(random.choice(templates), "Grammar: Transitions")

def generate_vocabulary_in_context() -> str:
    templates = [
        {
            "passage": "The politician's speech was known for its *equivocal* language, leaving both supporters and critics unsure of her actual stance on the controversial policy.",
            "question": "As used in the text, what does the word \"equivocal\" most nearly mean?",
            "correct": "Ambiguous",
            "distractors": ["Decisive", "Eloquent", "Aggressive"],
            "explanation": "The context clues 'leaving both supporters and critics unsure' and 'of her actual stance' indicate that her language was unclear or open to multiple interpretations. 'Ambiguous' is the best synonym for 'equivocal' in this context."
        },
        {
            "passage": "The author's *prolific* output astounded her peers; over the course of a single decade, she published fifteen novels and three collections of short stories.",
            "question": "As used in the text, what does the word \"prolific\" most nearly mean?",
            "correct": "Highly productive",
            "distractors": ["Complex", "Inconsistent", "Celebrated"],
            "explanation": "The context clue 'published fifteen novels and three collections of short stories' over a decade indicates a massive volume of work. Therefore, 'highly productive' is the best definition for 'prolific'."
        },
        {
            "passage": "Despite the team's best efforts to salvage the project, the fundamental flaws in its architecture rendered it *obsolete* before it even launched.",
            "question": "As used in the text, what does the word \"obsolete\" most nearly mean?",
            "correct": "Outdated and no longer useful",
            "distractors": ["Expensive", "Controversial", "Innovative"],
            "explanation": "The context describes 'fundamental flaws' that ruined the project, preventing it from being useful upon launch. 'Outdated and no longer useful' best fits the meaning of 'obsolete'."
        }
    ]
    q = random.choice(templates)
    return _format_question(q, "Vocabulary in Context")

def _format_question(q_data: dict, domain: str) -> str:
    options = [q_data["correct"]] + q_data["distractors"]
    random.shuffle(options)
    
    letters = ["A", "B", "C", "D"]
    labeled_options = list(zip(letters, options))
    
    correct_letter = next(l for l, v in labeled_options if v == q_data["correct"])
    options_str = " ".join(f"({l}) {v}" for l, v in labeled_options)
    
    question_text = q_data.get("question", "Which choice completes the text so that it conforms to the conventions of Standard English?")
    
    return (
        f"**Section:** Reading & Writing **Domain:** {domain}\n"
        f"**Passage/Context:** {q_data['passage']}\n"
        f"**Question:** {question_text}\n"
        f"**Options:** {options_str}\n"
        f"**Answer:** ({correct_letter}) {q_data['correct']}\n"
        f"**Explanation:** {q_data['explanation']}"
    )

def generate_programmatic_reading_question(message: str) -> str:
    msg_lower = message.lower()
    if "vocab" in msg_lower:
        return generate_vocabulary_in_context()
    if any(k in msg_lower for k in ["grammar", "verb", "transition"]):
        return random.choice([generate_grammar_subject_verb, generate_grammar_transition])()
    
    return random.choice([
        generate_grammar_subject_verb,
        generate_grammar_transition,
        generate_vocabulary_in_context
    ])()
