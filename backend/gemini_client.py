import json
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import get_gemini_api_key, get_gemini_model, gemini_enabled


SYSTEM_PROMPTS = {
    "sports": (
        "You are Sportly Bot, an AI-powered sports prediction and analysis assistant. "
        "You are dedicated EXCLUSIVELY to sports. You must answer queries related to sports, matches, players, teams, leagues, sports history, or sports predictions. "
        "First, determine if the user query is related to sports. Simple greetings like 'hello', 'hi', or 'how are you' are acceptable (respond by welcoming the user to the sports assistant). "
        "If the query is NOT related to sports (e.g. general knowledge, politics, geography, science, study guides, non-sports people/topics, coding, etc.), "
        "you MUST set the 'is_sports_related' field to false and set the 'direct_answer' field to exactly: 'I am Sportly, a specialized sports prediction and analysis assistant. I can only assist you with sports-related queries.' "
        "In this refusal case, ensure all other fields (explanation, action_steps, sources) are completely empty. "
        "When answering sports-related queries, consider team form, head-to-head records, player injuries, and recent performance. "
        "Make sure to show all clear details and answers with their exact answer. Do not use generic explanations; give precise, accurate, and comprehensive information. "
        "Always cite sources when providing information from web searches. Structure your answers clearly with bullet points when appropriate."
    ),
    "general": (
        "You are a helpful AI assistant. Answer questions clearly, accurately, and helpfully. "
        "Be conversational and friendly. If you're unsure about something, acknowledge it. "
        "Provide practical, actionable advice when appropriate."
    ),
}


def status() -> Dict[str, object]:
    return {"enabled": gemini_enabled(), "model": get_gemini_model() if gemini_enabled() else ""}


def generate_local_sports_answer(query: str, web_results: List[Dict[str, str]]) -> Dict[str, object]:
    """Generates an answer based on search results when Gemini API is offline."""
    if not web_results:
        return {
            "direct_answer": "I am Sportly, your sports assistant. I couldn't find any recent information on that sports topic. Could you please specify or try another query?",
            "explanation": "No web search results were found for the query.",
            "action_steps": [],
            "sources": [],
            "is_sports_related": True
        }
    
    paragraphs = []
    sources = []
    for res in web_results[:3]:
        snippet = res.get("snippet", "").strip()
        title = res.get("title", "").strip()
        url = res.get("url", "").strip()
        if snippet:
            paragraphs.append(f"{snippet} (Source: {title})")
        if url:
            sources.append(url)
            
    direct_answer = " ".join(paragraphs)
    
    return {
        "direct_answer": direct_answer,
        "explanation": f"This information was retrieved from live web search results for '{query}'.",
        "action_steps": ["Check the listed sources for full match highlights or statistics."],
        "sources": sources,
        "is_sports_related": True
    }


def generate_agent_answer(
    query: str,
    intent: str = "general",
    agent: str = "AI Assistant",
    retrieved_context: Optional[List[Dict[str, object]]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    web_results: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, object]]:
    if not gemini_enabled():
        return None

    context = format_context(retrieved_context or [])
    instructions = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["general"])
    
    # Build conversation history if provided
    history_text = ""
    if conversation_history:
        history_text = "\n".join([
            f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        history_text = f"\n\nConversation history:\n{history_text}\n"
    
    # Build web search context if provided
    web_search_text = ""
    if web_results:
        web_search_text = "\n\nWeb search results:\n" + "\n".join([
            f"- {r['title']}: {r['snippet']}\n  Source: {r['url']}"
            for r in web_results
        ])
    
    prompt = f"""
{instructions}

User query:
{query}
{history_text}
Retrieved context:
{context or "No additional context provided."}
{web_search_text}

Return only valid JSON with this exact shape:
{{
  "direct_answer": "your response to the user",
  "explanation": "any additional context or reasoning (optional)",
  "action_steps": ["step 1", "step 2"] or [],
  "sources": ["source1", "source2"] or [],
  "is_sports_related": true or false
}}

Rules:
- Be helpful, accurate, and conversational.
- Provide direct, actionable answers.
- If you need more information, ask clarifying questions.
- For research questions, cite sources when possible.
- Use web search results to provide accurate, up-to-date information.
- Keep responses concise but thorough.
""".strip()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
        }
    }
    raw = call_gemini_api(payload)
    text = extract_output_text(raw)
    return parse_answer_json(text)


def call_gemini_api(payload: Dict[str, object]) -> Dict[str, object]:
    model = get_gemini_model()
    api_key = get_gemini_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise GeminiError(exc.code, message) from exc


def extract_output_text(response: Dict[str, object]) -> str:
    try:
        candidates = response.get("candidates", [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts and len(parts) > 0:
                return parts[0].get("text", "")
    except Exception:
        pass
    return ""


def parse_answer_json(text: str) -> Dict[str, object]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    data = json.loads(cleaned)
    action_steps = data.get("action_steps", [])
    if isinstance(action_steps, str):
        action_steps = [action_steps]

    sources = data.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]

    return {
        "direct_answer": str(data.get("direct_answer", "")).strip(),
        "explanation": str(data.get("explanation", "")).strip(),
        "action_steps": [str(step).strip() for step in action_steps if str(step).strip()],
        "sources": [str(src).strip() for src in sources if str(src).strip()],
        "is_sports_related": bool(data.get("is_sports_related", True)),
    }


def format_context(rows: List[Dict[str, object]]) -> str:
    blocks = []
    for index, row in enumerate(rows, start=1):
        title = row.get("title", "Untitled")
        category = row.get("category", "general")
        content = row.get("content", "")
        blocks.append(f"[{index}] {title} ({category})\n{content}")
    return "\n\n".join(blocks)


def search_web(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo (free, no API key required)."""
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = []
        for result in ddgs.text(query, max_results=num_results):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })
        return results
    except ImportError:
        # If ddgs is not installed, return empty list
        return []
    except Exception as e:
        # Log error and return empty list
        print(f"Web search error: {e}")
        return []


class GeminiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Gemini error {status_code}: {message}")
