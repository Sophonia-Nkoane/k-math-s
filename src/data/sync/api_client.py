from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class SyncAPIClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        token: str,
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)

        data = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def upload(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/sync/upload", token=token, payload=payload)

    def download(self, token: str, cursor: str) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/sync/download", token=token, query={"cursor": cursor})

    def commit(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/api/v1/sync/commit", token=token, payload=payload)
