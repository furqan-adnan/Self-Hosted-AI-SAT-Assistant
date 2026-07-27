import os

class Settings:
    MODEL_PATH = os.environ.get("MODEL_PATH", "models/gemma-2-9b-it-Q4_K_M.gguf")
    LLM_CONTEXT_SIZE = int(os.environ.get("LLM_CONTEXT_SIZE", "3072"))
    LLM_THREADS = int(os.environ.get("LLM_THREADS", "2"))
    LLM_BATCH_SIZE = int(os.environ.get("LLM_BATCH_SIZE", "256"))
    CORPUS_PATH = os.environ.get("CORPUS_PATH", "cloud_corpus.json")
    MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "256"))
    TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.85"))
    RETRY_TEMPERATURE = float(os.environ.get("RETRY_TEMPERATURE", "0.5"))
    REPEAT_PENALTY = float(os.environ.get("REPEAT_PENALTY", "1.1"))
    DETECTION_WINDOW = int(os.environ.get("DETECTION_WINDOW", "120"))
    CONTEXT_TRUNCATION_LENGTH = int(os.environ.get("CONTEXT_TRUNCATION_LENGTH", "250"))
    STREAM_CHUNK_SIZE = int(os.environ.get("STREAM_CHUNK_SIZE", "24"))
    HISTORY_TRUNCATION_LENGTH = int(os.environ.get("HISTORY_TRUNCATION_LENGTH", "80"))
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "https://huggingface.co").split(",")

settings = Settings()
