from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from business.services.statement_document_service import StatementDocumentService
from business.services.statement_html_renderer import StatementHtmlRenderer
from business.services.statement_pdf_renderer import render_statement_pdf_bytes
from core.ports.repositories import FamilyRepoPort, LearnerRepoPort, PaymentRepoPort
from utils.settings_manager import SettingsManager


class StatementUseCase:
    def __init__(
        self,
        db_manager: Any,
        learner_repo: LearnerRepoPort,
        family_repo: FamilyRepoPort,
        payment_repo: PaymentRepoPort,
        template_dir: Optional[Path] = None,
    ) -> None:
        self.settings_manager = SettingsManager()
        self.statement_data_service = StatementDocumentService(
            db_manager=db_manager,
            learner_repository=learner_repo,
            payment_repository=payment_repo,
            family_repository=family_repo,
        )
        self.renderer = StatementHtmlRenderer(template_dir=template_dir)

    def _load_statement_settings(self) -> Dict[str, Any]:
        try:
            return self.settings_manager.load_statement_settings()
        except Exception:
            return {}

    def build_learner_statement_html(self, acc_no: str, generated_by: str) -> str:
        context_data = self.statement_data_service.get_learner_statement_data(acc_no, generated_by)
        if not context_data:
            return "<html><body><h2>Learner not found</h2></body></html>"
        return self.renderer.render(context_data=context_data, statement_settings=self._load_statement_settings())

    def build_family_statement_html(self, family_id: int, generated_by: str) -> str:
        context_data = self.statement_data_service.get_family_statement_data(family_id, generated_by)
        if not context_data:
            return "<html><body><h2>Family not found</h2></body></html>"
        return self.renderer.render(context_data=context_data, statement_settings=self._load_statement_settings())

    def render_pdf_bytes(self, html: str) -> bytes:
        return render_statement_pdf_bytes(html)
