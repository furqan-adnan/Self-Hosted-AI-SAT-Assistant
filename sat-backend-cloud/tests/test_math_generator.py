import re
from app.services.math_generator import (
    should_use_programmatic_math,
    generate_rate_problem,
    generate_linear_equation_problem,
    generate_percentage_problem,
    generate_average_problem,
    generate_programmatic_math_question
)

def test_should_use_programmatic_math():
    assert should_use_programmatic_math("give me a math practice question") == True
    assert should_use_programmatic_math("can you generate an algebra problem?") == True
    assert should_use_programmatic_math("give me a math question from my notes") == False
    assert should_use_programmatic_math("hello, how are you?") == False

def test_generate_rate_problem():
    question = generate_rate_problem()
    assert "**Section:** Math" in question
    assert "**Domain:** Problem Solving & Data Analysis" in question
    assert "**Passage/Context:**" in question
    assert "**Question:**" in question
    assert "**Options:**" in question
    assert "**Answer:**" in question
    assert "**Explanation:**" in question
    assert re.search(r'\*\*Answer:\*\*\s*\([A-D]\)', question)

def test_generate_linear_equation_problem():
    question = generate_linear_equation_problem()
    assert "**Section:** Math" in question
    assert "**Domain:** Heart of Algebra" in question
    assert "Solve the equation for x" in question

def test_generate_percentage_problem():
    question = generate_percentage_problem()
    assert "**Section:** Math" in question
    assert "items in stock" in question

def test_generate_average_problem():
    question = generate_average_problem()
    assert "**Section:** Math" in question
    assert "average score" in question

def test_generate_programmatic_math_question_dispatch():
    q1 = generate_programmatic_math_question("give me a percentage question")
    assert "items in stock" in q1
    
    q2 = generate_programmatic_math_question("give me an average question")
    assert "average score" in q2
    
    q3 = generate_programmatic_math_question("give me an algebra equation")
    assert "Solve the equation" in q3
