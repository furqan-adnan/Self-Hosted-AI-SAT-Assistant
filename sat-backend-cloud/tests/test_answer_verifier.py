from app.services.answer_verifier import verify_math_answer, chunk_text_for_pseudo_stream

def test_verify_math_answer_not_applicable():
    text = "This is a casual response, not a question."
    result, status = verify_math_answer(text)
    assert status == "not_applicable"
    assert result == text

def test_verify_math_answer_consistent():
    text = """**Section:** Math **Domain:** Algebra
**Passage/Context:** Solve for x: 2x = 10
**Question:** What is x?
**Options:** (A) 2 (B) 5 (C) 10 (D) 20
**Answer:** (B) 5
**Explanation:** Divide by 2: x = 5"""
    result, status = verify_math_answer(text)
    assert status == "consistent"
    assert result == text

def test_verify_math_answer_fixed():
    # The explanation says 5, but the Answer says (A) 2. It should be fixed to (B)
    text = """**Section:** Math **Domain:** Algebra
**Passage/Context:** Solve for x: 2x = 10
**Question:** What is x?
**Options:** (A) 2 (B) 5 (C) 10 (D) 20
**Answer:** (A) 2
**Explanation:** Divide by 2: x = 5"""
    result, status = verify_math_answer(text)
    assert status == "fixed"
    assert "(B) 2" in result or "(B)" in result # The regex will replace A with B
    # Verify the regex replace
    assert "**Answer:** (B) 2" in result

def test_verify_math_answer_unresolved_no_match():
    # The explanation computes a value that doesn't match any option
    text = """**Section:** Math **Domain:** Algebra
**Passage/Context:** Solve for x: 2x = 10
**Question:** What is x?
**Options:** (A) 2 (B) 4 (C) 6 (D) 8
**Answer:** (B) 4
**Explanation:** Divide by 2: x = 5"""
    result, status = verify_math_answer(text)
    assert status == "unresolved"

def test_verify_math_answer_unresolved_degenerate():
    # The explanation has a degenerate equation
    text = """**Section:** Math **Domain:** Algebra
**Passage/Context:** A problem
**Question:** What is x?
**Options:** (A) 2 (B) 5 (C) 10 (D) 20
**Answer:** (B) 5
**Explanation:** We set it up as 5x = 5x, so x = 5"""
    result, status = verify_math_answer(text)
    assert status == "unresolved"

def test_chunk_text_for_pseudo_stream():
    text = "123456789"
    chunks = list(chunk_text_for_pseudo_stream(text, chunk_size=3))
    assert chunks == ["123", "456", "789"]
