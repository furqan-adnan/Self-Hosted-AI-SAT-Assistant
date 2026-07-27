import json
import os
import pytest
import importlib
import app.config
import app.services.rag_service
from app.services.rag_service import retrieve_context

@pytest.fixture
def mock_corpus(tmp_path):
    corpus_data = [
        {"source": "doc1", "text": "This is a document about trigonometry, specifically sohcahtoa and angles."},
        {"source": "doc2", "text": "This document covers algebra, solving linear equations and finding x."}
    ]
    corpus_path = tmp_path / "cloud_corpus.json"
    with open(corpus_path, "w", encoding="utf-8") as f:
        json.dump(corpus_data, f)
    
    # Store old env var and set to test file
    old_path = os.environ.get("CORPUS_PATH", "cloud_corpus.json")
    os.environ["CORPUS_PATH"] = str(corpus_path)
    
    # Reload config and corpus for testing
    importlib.reload(app.config)
    importlib.reload(app.services.rag_service)
    
    yield
    
    # Cleanup
    os.environ["CORPUS_PATH"] = old_path
    importlib.reload(app.config)
    importlib.reload(app.services.rag_service)

def test_retrieve_context_no_match(mock_corpus):
    context, is_relevant = app.services.rag_service.retrieve_context("tell me a joke")
    assert is_relevant == False
    assert context == ""

def test_retrieve_context_match_trig(mock_corpus):
    context, is_relevant = app.services.rag_service.retrieve_context("how do I solve a trigonometry problem?")
    assert is_relevant == True
    assert "doc1" in context
    assert "sohcahtoa" in context

def test_retrieve_context_match_algebra(mock_corpus):
    context, is_relevant = app.services.rag_service.retrieve_context("help with linear equations")
    assert is_relevant == True
    assert "doc2" in context
    assert "linear equations" in context
