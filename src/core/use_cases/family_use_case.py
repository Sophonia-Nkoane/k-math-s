from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AuditRepoPort, FamilyRepoPort
from core.use_cases.pagination import sort_and_paginate


class FamilyUseCase:
    def __init__(self, family_repo: FamilyRepoPort, audit_repo: Optional[AuditRepoPort] = None) -> None:
        self.family_repo = family_repo
        self.audit_repo = audit_repo

    def list_families(self) -> List[Dict[str, Any]]:
        return self.family_repo.list_families()

    def list_families_paged(
        self,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "family_name",
        sort_dir: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_families()
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def get_family(self, family_id: int) -> Optional[Dict[str, Any]]:
        return self.family_repo.get_family(family_id)

    def create_family(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        if not payload.get("family_name"):
            return None, "family_name is required"

        family_id = self.family_repo.create_family(payload)
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="CREATE_FAMILY",
                object_type="Family",
                object_id=str(family_id),
                details=f"Created family {payload.get('family_name')}",
            )
        return family_id, None

    def update_family(self, family_id: int, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        if not payload.get("family_name"):
            return False, "family_name is required"
        ok = self.family_repo.update_family(family_id, payload)
        if not ok:
            return False, "Family update failed"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="UPDATE_FAMILY",
                object_type="Family",
                object_id=str(family_id),
                details=f"Updated family {payload.get('family_name')}",
            )
        return True, None

    def delete_family(self, family_id: int, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        ok = self.family_repo.delete_family(family_id)
        if not ok:
            return False, "Family deletion failed"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="DELETE_FAMILY",
                object_type="Family",
                object_id=str(family_id),
                details="Deleted family record",
            )
        return True, None
