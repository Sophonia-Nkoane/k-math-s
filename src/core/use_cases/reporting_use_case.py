from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories import PaymentRepoPort, LearnerRepoPort
from core.use_cases.pagination import sort_and_paginate


class ReportingUseCase:
    def __init__(self, learner_repo: LearnerRepoPort, payment_repo: PaymentRepoPort) -> None:
        self.learner_repo = learner_repo
        self.payment_repo = payment_repo

    def get_payment_statistics(
        self,
        month_year: Optional[str] = None,
        include_on_track: bool = True,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        target = month_year or datetime.now().strftime("%Y-%m")
        stats = self.payment_repo.get_payment_statistics(
            month_year=target,
            include_on_track=include_on_track,
            search=search,
        )
        stats["month_year"] = target
        stats["trends"] = self.payment_repo.get_payment_trends(months=12)
        return stats

    def get_payment_statistics_paged(
        self,
        month_year: Optional[str] = None,
        include_on_track: bool = True,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "surname",
        sort_dir: str = "asc",
    ) -> Dict[str, Any]:
        stats = self.get_payment_statistics(
            month_year=month_year,
            include_on_track=include_on_track,
            search=search,
        )
        rows = list(stats.get("rows") or [])
        items, total_count, total_pages, clean_page, clean_page_size = sort_and_paginate(
            rows,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )
        stats["rows"] = items
        stats["items"] = items
        stats["total_count"] = total_count
        stats["total_pages"] = total_pages
        stats["page"] = clean_page
        stats["page_size"] = clean_page_size
        stats["sort_by"] = sort_by
        stats["sort_dir"] = sort_dir
        return stats

    def get_class_list(self, grade: Optional[int] = None) -> Dict[str, Any]:
        if grade is not None:
            learners = self.learner_repo.list_learners_by_grade(grade)
            return {
                "mode": "grade",
                "grade": grade,
                "learners": learners,
            }

        rows = self.learner_repo.list_learners(is_active=True)
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for learner in rows:
            learner_grade = int(learner.get("grade") or 0)
            grouped.setdefault(learner_grade, []).append(learner)
        for grade_key in grouped.keys():
            grouped[grade_key] = sorted(
                grouped[grade_key],
                key=lambda r: (str(r.get("surname") or "").lower(), str(r.get("name") or "").lower()),
            )
        return {
            "mode": "school",
            "grades": dict(sorted(grouped.items(), key=lambda kv: kv[0])),
            "total_learners": len(rows),
        }
