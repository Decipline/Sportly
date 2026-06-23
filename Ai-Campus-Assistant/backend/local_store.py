from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from config import ROOT
from rag import chunk_text


DATA_DIR = ROOT / "data"
STORE_PATH = DATA_DIR / "local_store.json"


EMPTY_STORE = {
    "campus_documents": [],
    "campus_chunks": [],
    "admin_notices": [],
    "chat_messages": [],
}


class LocalStore:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        if not STORE_PATH.exists():
            self._write(EMPTY_STORE.copy())

    def list_rows(self, table: str, limit: int = 100) -> List[Dict[str, object]]:
        data = self._read()
        rows = list(data.get(table, []))
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return rows[:limit]

    def insert_document(self, title: str, category: str, content: str) -> Dict[str, object]:
        document = self._row({"title": title, "category": category, "content": content})
        data = self._read()
        data["campus_documents"].append(document)

        for chunk in chunk_text(content):
            data["campus_chunks"].append(
                self._row(
                    {
                        "document_id": document["id"],
                        "title": title,
                        "category": category,
                        "content": chunk,
                    }
                )
            )

        self._write(data)
        return document

    def insert_notice(self, title: str, audience: str, content: str, deadline: str = None) -> Dict[str, object]:
        notice = self._row(
            {
                "title": title,
                "audience": audience,
                "category": "notice",
                "content": content,
                "deadline": deadline,
            }
        )
        data = self._read()
        data["admin_notices"].append(notice)
        self._write(data)
        return notice

    def insert_chat(self, row: Dict[str, object]):
        data = self._read()
        data["chat_messages"].append(self._row(row))
        self._write(data)

    def _row(self, values: Dict[str, object]) -> Dict[str, object]:
        return {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **values,
        }

    def _read(self) -> Dict[str, List[Dict[str, object]]]:
        try:
            data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            data = EMPTY_STORE.copy()

        for key in EMPTY_STORE:
            data.setdefault(key, [])
        return data

    def _write(self, data: Dict[str, List[Dict[str, object]]]):
        STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
