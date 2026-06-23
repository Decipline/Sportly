import json
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import get_openai_api_key, get_openai_model, openai_enabled


SYSTEM_PROMPTS = {
    "sports_general": (
        "You are Sportly, an AI-powered sports assistant. Help with sports-related questions, "
        "match information, team performance, player statistics, and general sports knowledge. "
        "Focus on football, basketball, cricket, tennis, and other major sports. "
        "Be conversational and knowledgeable about current and historical sports data. "
        "If you're unsure about specific recent scores or results, acknowledge it."
    ),
    "sports_score": (
        "You are Sportly, a sports score specialist. Provide accurate information about "
        "match scores, game results, standings, league tables, and tournament outcomes. "
        "Focus on providing current and recent score information. "
        "If you don't have real-time data, acknowledge the limitation and suggest where to find current scores."
    ),
    "sports_prediction": (
        "You are Sportly, a sports prediction analyst. Help with match predictions, "
        "team performance analysis, odds interpretation, and probability assessments. "
        "Provide balanced analysis based on available data, team form, head-to-head records, "
        "and relevant factors. Always include appropriate disclaimers that predictions are not guarantees."
    ),
    "sports_player": (
        "You are Sportly, a player information specialist. Provide details about "
        "player statistics, performance metrics, transfer news, injury updates, "
        "contract information, and career achievements. "
        "Focus on factual information and recent performance data."
    ),
    "general": (
        "You are Sportly, a sports-focused AI assistant. Answer sports-related questions "
        "clearly, accurately, and helpfully. If a question is not sports-related, "
        "politely redirect to sports topics or acknowledge the limitation."
    ),
}


def status() -> Dict[str, object]:
    return {"enabled": openai_enabled(), "model": get_openai_model() if openai_enabled() else ""}


def generate_agent_answer(
    query: str,
    intent: str = "general",
    agent: str = "AI Assistant",
    retrieved_context: Optional[List[Dict[str, object]]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, object]]:
    if not openai_enabled():
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
    
    prompt = f"""
{instructions}

User query:
{query}
{history_text}
Retrieved context:
{context or "No additional context provided."}

Return only valid JSON with this exact shape:
{{
  "direct_answer": "your response to the user",
  "explanation": "any additional context or reasoning (optional)",
  "action_steps": ["step 1", "step 2"] or [],
  "sources": ["source1", "source2"] or []
}}

Rules:
- Be helpful, accurate, and conversational.
- Provide direct, actionable answers.
- If you need more information, ask clarifying questions.
- For coding questions, provide working code examples.
- For research questions, cite sources when possible.
- Keep responses concise but thorough.
""".strip()

    payload = {
        "model": get_openai_model(),
        "input": prompt,
        "max_output_tokens": 1000,
    }
    raw = call_responses_api(payload)
    text = extract_output_text(raw)
    return parse_answer_json(text)


def call_responses_api(payload: Dict[str, object]) -> Dict[str, object]:
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {get_openai_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise OpenAIError(exc.code, message) from exc


def extract_output_text(response: Dict[str, object]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


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
    """Search the web using a simple approach (placeholder for actual web search API)."""
    # This is a placeholder - in production, you'd use a real search API like:
    # - Google Custom Search API
    # - Bing Search API
    # - DuckDuckGo API
    # - SerpAPI
    
    # For now, return empty list - user can integrate their preferred search API
    return []


def extract_from_url(url: str) -> Optional[Dict[str, object]]:
    """Extract content from a URL (placeholder for web scraping)."""
    # This is a placeholder - in production, you'd use:
    # - requests + BeautifulSoup
    # - scrapy
    # - newspaper3k
    # - trafilatura
    
    # For now, return None - user can integrate their preferred scraping library
    return None


def extract_document_metadata(content: str, title: str = "") -> Optional[Dict[str, object]]:
    """Automatically extract metadata from document content using OpenAI."""
    if not openai_enabled():
        return None

    prompt = f"""
Analyze the following document content and extract metadata.

Document title: {title or "Untitled"}
Document content:
{content[:3000]}

Return only valid JSON with this exact shape:
{{
  "suggested_category": "syllabus|notice|rules|fees|general",
  "key_topics": ["topic1", "topic2", "topic3"],
  "summary": "brief 2-3 sentence summary",
  "important_dates": ["date1", "date2"] or [],
  "department": "department name or null"
}}
""".strip()

    payload = {
        "model": get_openai_model(),
        "input": prompt,
        "max_output_tokens": 500,
    }
    
    try:
        raw = call_responses_api(payload)
        text = extract_output_text(raw)
        return parse_json_safely(text)
    except Exception:
        return None


def extract_notice_metadata(content: str, title: str = "") -> Optional[Dict[str, object]]:
    """Automatically extract metadata from notice content using OpenAI."""
    if not openai_enabled():
        return None

    prompt = f"""
Analyze the following notice and extract key information.

Notice title: {title or "Untitled"}
Notice content:
{content[:3000]}

Return only valid JSON with this exact shape:
{{
  "suggested_audience": "all|BCA|CSIT|BBA|specific semester",
  "deadline": "YYYY-MM-DD or null",
  "priority": "high|medium|low",
  "action_required": "what students need to do",
  "department": "department name or null"
}}
""".strip()

    payload = {
        "model": get_openai_model(),
        "input": prompt,
        "max_output_tokens": 400,
    }
    
    try:
        raw = call_responses_api(payload)
        text = extract_output_text(raw)
        return parse_json_safely(text)
    except Exception:
        return None


def enhance_query(query: str) -> Optional[Dict[str, object]]:
    """Enhance user query with context expansion using OpenAI."""
    if not openai_enabled():
        return None

    prompt = f"""
Analyze the following student query and enhance it for better understanding.

Original query: {query}

Return only valid JSON with this exact shape:
{{
  "clarified_query": "more specific version of the query",
  "missing_info": ["info1", "info2"] or [],
  "suggested_context": "what context would help answer this",
  "intent_confidence": "high|medium|low"
}}
""".strip()

    payload = {
        "model": get_openai_model(),
        "input": prompt,
        "max_output_tokens": 300,
    }
    
    try:
        raw = call_responses_api(payload)
        text = extract_output_text(raw)
        return parse_json_safely(text)
    except Exception:
        return None


def parse_json_safely(text: str) -> Dict[str, object]:
    """Safely parse JSON from OpenAI response with cleanup."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


class OpenAIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"OpenAI error {status_code}: {message}")
