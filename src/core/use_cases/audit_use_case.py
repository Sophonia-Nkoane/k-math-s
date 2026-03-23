from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AuditRepoPort
from core.use_cases.pagination import sort_and_paginate


class AuditUseCase:
    def __init__(self, audit_repo: AuditRepoPort) -> None:
        self.audit_repo = audit_repo

    def list_audit(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        username: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = self.audit_repo.list_audit(
            limit=None,
            start_date=start_date,
            end_date=end_date,
            action_type=action_type,
            username=username,
            search=search,
        )

        normalized: List[Dict[str, Any]] = []
        for row in rows:
            entry = dict(row)
            timestamp = entry.get("timestamp")
            if hasattr(timestamp, "isoformat"):
                entry["timestamp"] = timestamp.isoformat(timespec="seconds")
            elif timestamp is not None:
                entry["timestamp"] = str(timestamp).replace(" ", "T", 1)
            else:
                entry["timestamp"] = ""
            entry["username"] = str(entry.get("username") or "System")
            normalized.append(entry)
        return normalized

    def list_audit_paged(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        username: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "timestamp",
        sort_dir: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_audit(
            start_date=start_date,
            end_date=end_date,
            action_type=action_type,
            username=username,
            search=search,
        )
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)
