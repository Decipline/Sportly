import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from server import is_sports_query_local


def test_sports_classifier():
    # Test valid sports queries
    assert is_sports_query_local("Who won the 2026 IPL?") == True
    assert is_sports_query_local("football world cup schedule") == True
    assert is_sports_query_local("How many runs did Kohli score?") == True
    assert is_sports_query_local("wwe wrestlemania match card") == True
    assert is_sports_query_local("raw and smackdown scores") == True
    
    # Test greetings (should be allowed)
    assert is_sports_query_local("hello") == True
    assert is_sports_query_local("Hi") == True
    
    # Test non-sports queries (should be blocked)
    assert is_sports_query_local("Who is Rajesh Hamal?") == False
    assert is_sports_query_local("How to study DSA") == False
    assert is_sports_query_local("What is database normalization?") == False


if __name__ == "__main__":
    test_sports_classifier()
    print("All tests passed successfully.")
