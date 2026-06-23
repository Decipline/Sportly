import re
from typing import Dict, Iterable, List


def chunk_text(text: str, max_words: int = 120) -> List[str]:
    words = re.findall(r"\S+", text)
    chunks = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start : start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def terms(text: str) -> List[str]:
    stopwords = {
        "about",
        "after",
        "answer",
        "before",
        "does",
        "from",
        "have",
        "need",
        "question",
        "tell",
        "that",
        "the",
        "this",
        "what",
        "when",
        "where",
        "with",
    }
    raw = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [word for word in raw if len(word) > 2 and word not in stopwords]


def rank_context(query: str, rows: Iterable[Dict[str, object]], limit: int = 5) -> List[Dict[str, object]]:
    query_terms = terms(query)
    scored = []

    for row in rows:
        content = str(row.get("content", ""))
        title = str(row.get("title", ""))
        haystack = f"{title} {content}".lower()
        score = sum(1 for term in query_terms if term in haystack)
        if score:
            scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]
