import re

def regex_tokenize(text: str):
    return re.findall(r'\w+', text.lower())

BM25_STOPWORDS = {
    "explain", "from", "my", "notes", "give", "me", "a", "question", 
    "to", "solve", "hi", "hello", "hey", "test", "practice", "ask", 
    "want", "find", "show", "what", "is", "how", "do", "you", "can", "portion"
}

VALID_DOMAINS = ["trigonometry", "algebra", "equations", "maths", "math", "geometry", "shapes", "percent", "percentage", "statistics"]
