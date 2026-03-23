from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import AuditRepoPort, PaymentRepoPort
from core.use_cases.pagination import sort_and_paginate


class PaymentUseCase:
    def __init__(self, payment_repo: PaymentRepoPort, audit_repo: Optional[AuditRepoPort] = None) -> None:
        self.payment_repo = payment_repo
        self.audit_repo = audit_repo

    def list_payments(
        self,
        learner_acc_no: Optional[str] = None,
        family_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self.payment_repo.list_payments(learner_acc_no=learner_acc_no, family_id=family_id, limit=limit)

    def list_payments_paged(
        self,
        learner_acc_no: Optional[str] = None,
        family_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "date",
        sort_dir: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        # Repository currently exposes limit-based listing only; use a large server-side limit and paginate in use case.
        rows = self.payment_repo.list_payments(learner_acc_no=learner_acc_no, family_id=family_id, limit=1_000_000)
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def create_payment(self, payload: Dict[str, Any], user_id: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        if payload.get("amount") in (None, ""):
            return None, "amount is required"
        if not payload.get("date"):
            return None, "date is required"

        payment_id = self.payment_repo.create_payment(payload)
        object_id = payload.get("learner_id") or payload.get("family_id") or str(payment_id)

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="CREATE_PAYMENT",
                object_type="Payment",
                object_id=str(object_id),
                details=f"Recorded payment of {payload.get('amount')}",
            )

        return payment_id, None

    def delete_payment(self, payment_id: int, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        if not payment_id:
            return False, "payment_id is required"

        ok = self.payment_repo.delete_payment(int(payment_id))
        if not ok:
            return False, "Payment deletion failed"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="DELETE_PAYMENT",
                object_type="Payment",
                object_id=str(payment_id),
                details="Deleted payment",
            )

        return True, None

    def get_learner_balance(self, acc_no: str) -> float:
        return self.payment_repo.get_balance_for_learner(acc_no)

    def get_family_balance(self, family_id: int) -> float:
        return self.payment_repo.get_balance_for_family(family_id)
