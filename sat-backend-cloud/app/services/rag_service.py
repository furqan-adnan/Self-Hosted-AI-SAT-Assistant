import os
import json
import re
import difflib
import numpy as np
from typing import Tuple
from rank_bm25 import BM25Okapi
from app.config import settings
from app.core.tokenizer import regex_tokenize, BM25_STOPWORDS, VALID_DOMAINS

corpus = []
bm25 = None

if os.path.exists(settings.CORPUS_PATH):
    try:
        with open(settings.CORPUS_PATH, "r", encoding="utf-8") as f:
            corpus = json.load(f)
        
        tokenized_corpus = [regex_tokenize(doc["text"]) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        print(f"✅ RAG Engine Active: Loaded {len(corpus)} full-page text nodes.", flush=True)
        
    except Exception as e:
        print(f"⚠️ Failed to compile RAG index: {e}", flush=True)
else:
    print(f"⚠️ '{settings.CORPUS_PATH}' not found. Operating in standard tutor mode.", flush=True)

def retrieve_context(message: str) -> Tuple[str, bool]:
    context_str = ""
    is_relevant = False

    if bm25 is not None and len(corpus) > 0:
        raw_tokens = regex_tokenize(message)
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
                    
                    truncated_text = matched_page['text'][:settings.CONTEXT_TRUNCATION_LENGTH]
                    if len(matched_page['text']) > settings.CONTEXT_TRUNCATION_LENGTH:
                        truncated_text += "..."
                        
                    context_segments.append(
                        f"--- Reference Material [{matched_page['source']}] ---\n"
                        f"{truncated_text}"
                    )
            
            if is_relevant:
                context_str = "\n\n".join(context_segments)
    
    return context_str, is_relevant
