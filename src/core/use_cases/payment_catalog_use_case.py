from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AuditRepoPort, PaymentRepoPort
from core.use_cases.pagination import sort_and_paginate


class PaymentCatalogUseCase:
    def __init__(self, payment_repo: PaymentRepoPort, audit_repo: Optional[AuditRepoPort] = None) -> None:
        self.payment_repo = payment_repo
        self.audit_repo = audit_repo

    def list_payment_options(self) -> List[Dict[str, Any]]:
        return self.payment_repo.list_payment_options()

    def list_payment_options_paged(
        self,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "grade",
        sort_dir: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_payment_options()
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def create_payment_option(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        required = ["option_name", "subjects_count", "grade", "monthly_fee"]
        missing = [field for field in required if payload.get(field) in (None, "")]
        if missing:
            return None, f"Missing required fields: {', '.join(missing)}"
        option_name = str(payload.get("option_name") or "").strip()
        subjects_count = int(payload.get("subjects_count") or 0)
        grade = int(payload.get("grade") or 0)
        if not option_name:
            return None, "option_name is required"
        if subjects_count <= 0:
            return None, "subjects_count must be greater than 0"
        if grade <= 0:
            return None, "grade must be greater than 0"

        existing = self.payment_repo.list_payment_options()
        duplicate = next(
            (
                row
                for row in existing
                if str(row.get("option_name") or "").strip().lower() == option_name.lower()
                and int(row.get("subjects_count") or 0) == subjects_count
                and int(row.get("grade") or 0) == grade
            ),
            None,
        )
        if duplicate:
            return None, "Payment option already exists for this grade and subject count"

        payload["option_name"] = option_name
        try:
            option_id = self.payment_repo.create_payment_option(payload)
        except Exception as exc:
            return None, str(exc)
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="CREATE_PAYMENT_OPTION",
                object_type="PaymentOptions",
                object_id=str(option_id),
                details=f"Created payment option {payload.get('option_name')}",
            )
        return option_id, None

    def update_payment_option(self, option_id: int, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        option_name = str(payload.get("option_name") or "").strip()
        subjects_count = int(payload.get("subjects_count") or 0)
        grade = int(payload.get("grade") or 0)
        if not option_name:
            return False, "option_name is required"
        if subjects_count <= 0:
            return False, "subjects_count must be greater than 0"
        if grade <= 0:
            return False, "grade must be greater than 0"

        existing = self.payment_repo.list_payment_options()
        duplicate = next(
            (
                row
                for row in existing
                if int(row.get("id") or 0) != int(option_id)
                and str(row.get("option_name") or "").strip().lower() == option_name.lower()
                and int(row.get("subjects_count") or 0) == subjects_count
                and int(row.get("grade") or 0) == grade
            ),
            None,
        )
        if duplicate:
            return False, "Another payment option already exists with the same name/grade/subjects"

        payload["option_name"] = option_name
        try:
            ok = self.payment_repo.update_payment_option(option_id, payload)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Payment option update failed"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="UPDATE_PAYMENT_OPTION",
                object_type="PaymentOptions",
                object_id=str(option_id),
                details="Updated payment option",
            )
        return True, None

    def delete_payment_option(self, option_id: int, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        ok = self.payment_repo.delete_payment_option(option_id)
        if not ok:
            return False, "Payment option is in use or could not be deleted"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="DELETE_PAYMENT_OPTION",
                object_type="PaymentOptions",
                object_id=str(option_id),
                details="Deleted payment option",
            )
        return True, None

    def list_payment_terms(self) -> List[Dict[str, Any]]:
        return self.payment_repo.list_payment_terms()

    def list_payment_terms_paged(
        self,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "term_name",
        sort_dir: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_payment_terms()
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def create_payment_term(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        term_name = str(payload.get("term_name") or "").strip()
        if not term_name:
            return None, "term_name is required"

        existing = self.payment_repo.list_payment_terms()
        duplicate = next(
            (row for row in existing if str(row.get("term_name") or "").strip().lower() == term_name.lower()),
            None,
        )
        if duplicate:
            return None, "Payment term already exists"

        payload["term_name"] = term_name
        try:
            term_id = self.payment_repo.create_payment_term(payload)
        except Exception as exc:
            return None, str(exc)
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="CREATE_PAYMENT_TERM",
                object_type="PaymentTerms",
                object_id=str(term_id),
                details=f"Created payment term {payload.get('term_name')}",
            )
        return term_id, None

    def update_payment_term(self, term_id: int, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        term_name = str(payload.get("term_name") or "").strip()
        if not term_name:
            return False, "term_name is required"
        existing = self.payment_repo.list_payment_terms()
        duplicate = next(
            (
                row
                for row in existing
                if int(row.get("term_id") or 0) != int(term_id)
                and str(row.get("term_name") or "").strip().lower() == term_name.lower()
            ),
            None,
        )
        if duplicate:
            return False, "Another payment term already exists with this name"

        payload["term_name"] = term_name
        try:
            ok = self.payment_repo.update_payment_term(term_id, payload)
        except Exception as exc:
            return False, str(exc)
        if not ok:
            return False, "Payment term update failed"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="UPDATE_PAYMENT_TERM",
                object_type="PaymentTerms",
                object_id=str(term_id),
                details="Updated payment term",
            )
        return True, None

    def delete_payment_term(self, term_id: int, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        ok = self.payment_repo.delete_payment_term(term_id)
        if not ok:
            return False, "Payment term is in use or could not be deleted"
        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="DELETE_PAYMENT_TERM",
                object_type="PaymentTerms",
                object_id=str(term_id),
                details="Deleted payment term",
            )
        return True, None
