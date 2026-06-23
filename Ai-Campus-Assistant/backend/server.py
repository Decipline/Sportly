from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

from config import APP_PORT, set_env_value
from local_store import LocalStore
from openai_client import (
    OpenAIError,
    extract_document_metadata,
    extract_notice_metadata,
    generate_agent_answer,
    search_web,
    status as openai_status,
)
from rag import chunk_text, rank_context
from supabase_client import SupabaseClient, SupabaseError


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DB = SupabaseClient()
LOCAL = LocalStore()


class CampusAssistantHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_POST(self):
        try:
            if self.path == "/api/ask":
                self.handle_ask()
                return
            if self.path == "/api/documents":
                self.handle_create_document()
                return
            if self.path == "/api/notices":
                self.handle_create_notice()
                return
            if self.path == "/api/settings/openai":
                self.handle_openai_settings()
                return
            if self.path == "/api/extract/document":
                self.handle_extract_document()
                return
            if self.path == "/api/extract/notice":
                self.handle_extract_notice()
                return
            if self.path == "/api/enhance/query":
                self.handle_enhance_query()
                return

            self.send_error(404, "Not found")
        except json.JSONDecodeError:
            self.respond_json({"error": "Invalid JSON body."}, status=400)
        except Exception as exc:
            self.respond_json({"error": str(exc)}, status=500)

    def do_GET(self):
        try:
            if self.path == "/api/health":
                self.respond_json(
                    {
                        "ok": True,
                        "database": DB.status(),
                        "openai": openai_status(),
                        "local_store": {"enabled": True},
                    }
                )
                return
            if self.path == "/api/documents":
                self.respond_json({"documents": self.list_documents()})
                return
            if self.path == "/api/notices":
                self.respond_json({"notices": self.list_notices()})
                return

            super().do_GET()
        except Exception as exc:
            self.respond_json({"error": str(exc)}, status=500)

    def handle_ask(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
        query = payload.get("query", "")
        conversation_history = payload.get("conversation_history", [])

        if not query.strip():
            self.respond_json(
                {
                    "error": "Query is required.",
                },
                status=400,
            )
            return

        # Determine intent based on query content
        intent = self.classify_intent(query)
        
        # Search web if needed (placeholder - returns empty for now)
        web_results = search_web(query) if "search" in query.lower() or "find" in query.lower() else []
        
        # Retrieve relevant context from stored documents
        retrieved = []
        context = ""
        chunks = self.list_chunks()
        notices = [
            {
                "title": row.get("title"),
                "category": "notice",
                "content": row.get("content"),
            }
            for row in self.list_notices()
        ]
        retrieved = rank_context(query, [*chunks, *notices])
        context = "\n".join(str(row.get("content", "")) for row in retrieved)

        # Generate AI response
        ai_answer = None
        try:
            ai_answer = generate_agent_answer(
                query=query,
                intent=intent,
                agent="Sportly",
                retrieved_context=retrieved,
                conversation_history=conversation_history,
            )
        except (OpenAIError, json.JSONDecodeError) as exc:
            result = {
                "error": str(exc),
                "generated_by": "error",
            }
            self.respond_json(result, status=500)
            return

        if ai_answer:
            result = {
                "answer": ai_answer,
                "generated_by": "openai",
                "intent": intent,
                "agent": "Sportly",
            }
        else:
            result = {
                "answer": {
                    "direct_answer": "OpenAI is not configured. Please add your OpenAI API key to use AI features.",
                    "explanation": "",
                    "action_steps": ["Add OPENAI_API_KEY to your .env file"],
                    "sources": [],
                },
                "generated_by": "local",
                "intent": intent,
                "agent": "Sportly",
            }

        result["retrieved_context"] = [
            {
                "title": row.get("title"),
                "category": row.get("category"),
                "content": row.get("content"),
            }
            for row in retrieved
        ]

        if web_results:
            result["web_results"] = web_results

        # Save to local storage
        LOCAL.insert_chat(
            {
                "user_query": query,
                "intent": intent,
                "agent": "Sportly",
                "answer": result["answer"],
            }
        )
        
        # Save to Supabase if enabled
        if DB.enabled:
            try:
                DB.insert_row(
                    "chat_messages",
                    {
                        "user_query": query,
                        "intent": intent,
                        "agent": "Sportly",
                        "answer": result["answer"],
                    },
                )
            except SupabaseError:
                result["database_warning"] = "Chat history was not saved because Supabase tables are not ready."

        self.respond_json(result)
    
    def classify_intent(self, query: str) -> str:
        """Simple intent classification for sports-focused assistant."""
        text = query.lower()
        
        if any(term in text for term in ["score", "goal", "match", "game", "win", "lose", "team", "player", "tournament", "league", "championship", "cup", "final", "result", "standings", "table", "ranking"]):
            return "sports_score"
        if any(term in text for term in ["predict", "prediction", "forecast", "odds", "bet", "chance", "probability", "likely", "expect", "analysis"]):
            return "sports_prediction"
        if any(term in text for term in ["player", "coach", "manager", "transfer", "contract", "injury", "suspension", "stats", "statistics", "performance"]):
            return "sports_player"
        if any(term in text for term in ["football", "soccer", "basketball", "cricket", "tennis", "baseball", "hockey", "rugby", "golf", "formula", "f1", "nfl", "nba", "mlb", "nhl"]):
            return "sports_general"
        return "sports_general"

    def handle_create_document(self):
        payload = self.read_json_body()
        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "general")).strip() or "general"
        content = str(payload.get("content", "")).strip()

        if not title or not content:
            self.respond_json({"error": "Document title and content are required."}, status=400)
            return

        # Auto-extract metadata using OpenAI if enabled
        extracted_metadata = extract_document_metadata(content, title)
        if extracted_metadata:
            if extracted_metadata.get("suggested_category"):
                category = extracted_metadata["suggested_category"]
        
        if not DB.enabled:
            document = LOCAL.insert_document(title, category, content)
            response_data = {
                "document": document,
                "chunks_created": len(chunk_text(content)),
                "stored_in": "local",
            }
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)
            return

        try:
            document = DB.insert_row(
                "campus_documents",
                {"title": title, "category": category, "content": content},
            )
            document_id = document.get("id")
            chunks = [
                {
                    "document_id": document_id,
                    "title": title,
                    "category": category,
                    "content": chunk,
                }
                for chunk in chunk_text(content)
            ]
            DB.insert_rows("campus_chunks", chunks)
            LOCAL.insert_document(title, category, content)
            response_data = {
                "document": document,
                "chunks_created": len(chunks),
                "stored_in": "supabase",
            }
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)
        except SupabaseError as exc:
            document = LOCAL.insert_document(title, category, content)
            response_data = {
                "document": document,
                "chunks_created": len(chunk_text(content)),
                "stored_in": "local",
                "warning": str(exc),
            }
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)

    def handle_create_notice(self):
        payload = self.read_json_body()
        title = str(payload.get("title", "")).strip()
        audience = str(payload.get("audience", "all")).strip() or "all"
        content = str(payload.get("content", "")).strip()
        deadline = str(payload.get("deadline", "")).strip() or None

        if not title or not content:
            self.respond_json({"error": "Notice title and content are required."}, status=400)
            return

        # Auto-extract metadata using OpenAI if enabled
        extracted_metadata = extract_notice_metadata(content, title)
        if extracted_metadata:
            if extracted_metadata.get("suggested_audience"):
                audience = extracted_metadata["suggested_audience"]
            if extracted_metadata.get("deadline") and not deadline:
                deadline = extracted_metadata["deadline"]
        
        if not DB.enabled:
            notice = LOCAL.insert_notice(title, audience, content, deadline)
            response_data = {"notice": notice, "stored_in": "local"}
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)
            return

        try:
            notice = DB.insert_row(
                "admin_notices",
                {"title": title, "audience": audience, "content": content, "deadline": deadline},
            )
            LOCAL.insert_notice(title, audience, content, deadline)
            response_data = {"notice": notice, "stored_in": "supabase"}
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)
        except SupabaseError as exc:
            notice = LOCAL.insert_notice(title, audience, content, deadline)
            response_data = {"notice": notice, "stored_in": "local", "warning": str(exc)}
            if extracted_metadata:
                response_data["extracted_metadata"] = extracted_metadata
            self.respond_json(response_data, status=201)

    def handle_openai_settings(self):
        payload = self.read_json_body()
        api_key = str(payload.get("api_key", "")).strip()
        model = str(payload.get("model", "gpt-4.1-mini")).strip() or "gpt-4.1-mini"
        if not api_key:
            self.respond_json({"error": "OpenAI API key is required."}, status=400)
            return

        set_env_value("OPENAI_API_KEY", api_key)
        set_env_value("OPENAI_MODEL", model)
        self.respond_json({"openai": openai_status()})

    def handle_extract_document(self):
        payload = self.read_json_body()
        content = str(payload.get("content", "")).strip()
        title = str(payload.get("title", "")).strip()

        if not content:
            self.respond_json({"error": "Document content is required."}, status=400)
            return

        metadata = extract_document_metadata(content, title)
        if metadata:
            self.respond_json({"metadata": metadata, "enabled": True})
        else:
            self.respond_json({"metadata": None, "enabled": False, "warning": "OpenAI not configured or extraction failed"})

    def handle_extract_notice(self):
        payload = self.read_json_body()
        content = str(payload.get("content", "")).strip()
        title = str(payload.get("title", "")).strip()

        if not content:
            self.respond_json({"error": "Notice content is required."}, status=400)
            return

        metadata = extract_notice_metadata(content, title)
        if metadata:
            self.respond_json({"metadata": metadata, "enabled": True})
        else:
            self.respond_json({"metadata": None, "enabled": False, "warning": "OpenAI not configured or extraction failed"})

    def handle_enhance_query(self):
        payload = self.read_json_body()
        query = str(payload.get("query", "")).strip()

        if not query:
            self.respond_json({"error": "Query is required."}, status=400)
            return

        enhancement = enhance_query(query)
        if enhancement:
            self.respond_json({"enhancement": enhancement, "enabled": True})
        else:
            self.respond_json({"enhancement": None, "enabled": False, "warning": "OpenAI not configured or enhancement failed"})

    def list_documents(self):
        return self.merge_rows([*self.supabase_rows("campus_documents", 100), *LOCAL.list_rows("campus_documents", 100)])

    def list_chunks(self):
        return self.merge_rows([*self.supabase_rows("campus_chunks", 500), *LOCAL.list_rows("campus_chunks", 500)])

    def list_notices(self):
        return self.merge_rows([*self.supabase_rows("admin_notices", 100), *LOCAL.list_rows("admin_notices", 100)])

    def supabase_rows(self, table: str, limit: int):
        if not DB.enabled:
            return []
        return DB.safe_list_rows(table, limit=limit, order="created_at.desc")

    def merge_rows(self, rows):
        seen = set()
        merged = []
        for row in rows:
            key = (row.get("title"), row.get("content"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
        return merged

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def respond_json(self, data, status=200):
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else APP_PORT
    server = ThreadingHTTPServer(("localhost", port), CampusAssistantHandler)
    print(f"AI Campus Assistant running at http://localhost:{port}")
    print(f"Supabase enabled: {DB.enabled}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
