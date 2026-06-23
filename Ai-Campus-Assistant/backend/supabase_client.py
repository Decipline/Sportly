import json
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, supabase_enabled


class SupabaseClient:
    def __init__(self):
        self.enabled = supabase_enabled()
        self.url = SUPABASE_URL
        self.key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

    def status(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "url": self.url if self.enabled else "",
            "using_service_key": bool(SUPABASE_SERVICE_ROLE_KEY),
        }

    def list_rows(self, table: str, limit: int = 100, order: Optional[str] = None) -> List[Dict[str, object]]:
        if not self.enabled:
            return []

        params = {"select": "*", "limit": str(limit)}
        if order:
            params["order"] = order
        return self._request("GET", table, params=params)

    def safe_list_rows(self, table: str, limit: int = 100, order: Optional[str] = None) -> List[Dict[str, object]]:
        try:
            return self.list_rows(table, limit=limit, order=order)
        except SupabaseError:
            return []

    def insert_row(self, table: str, row: Dict[str, object]) -> Dict[str, object]:
        rows = self.insert_rows(table, [row])
        return rows[0] if rows else {}

    def insert_rows(self, table: str, rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
        if not self.enabled:
            return []
        return self._request("POST", table, data=rows)

    def _request(
        self,
        method: str,
        table: str,
        params: Optional[Dict[str, str]] = None,
        data: Optional[object] = None,
    ):
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self.url}/rest/v1/{table}{query}"
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=15) as response:
                content = response.read().decode("utf-8")
                if not content:
                    return []
                return json.loads(content)
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise SupabaseError(exc.code, message) from exc


class SupabaseError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.clean_message())

    def clean_message(self) -> str:
        if self.status_code == 404:
            return (
                "Supabase table not found. Run database/supabase_schema.sql in the Supabase SQL Editor, "
                "then refresh this app."
            )
        return f"Supabase error {self.status_code}: {self.message}"
