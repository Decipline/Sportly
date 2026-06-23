import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app_logic import answer_query, classify_intent


def test_intent_classifier():
    assert classify_intent("Make a 7 day study plan for DBMS") == "study_plan"
    assert classify_intent("What is the exam schedule?") == "admin"
    assert classify_intent("When is the internal exam?") == "admin"
    assert classify_intent("how to study dsa") == "study_plan"
    assert classify_intent("Give me career advice") == "advisor"
    assert classify_intent("What is artificial intelligence?") == "knowledge"


def test_context_answer():
    result = answer_query(
        "What does the notice say about admit cards?",
        "Students must collect admit cards before July 8. Admit cards are required for exam hall entry.",
    )
    assert "admit cards" in result["answer"]["direct_answer"].lower()


def test_all_agents_have_outputs():
    samples = [
        ("Explain DBMS normalization", "Knowledge Agent"),
        ("How to study DSA", "Study Planner Agent"),
        ("When is the internal exam?", "Admin Help Agent"),
        ("I am confused about my career", "Advisor Agent"),
    ]
    for query, agent in samples:
        result = answer_query(query)
        assert result["agent"] == agent
        assert result["answer"]["direct_answer"]


if __name__ == "__main__":
    test_intent_classifier()
    test_context_answer()
    test_all_agents_have_outputs()
    print("All tests passed.")
