import sys
import logging
from pathlib import Path

from business.services.statement_document_service import StatementDocumentService
from business.services.statement_html_renderer import StatementHtmlRenderer

logger = logging.getLogger(__name__)


def _resolve_shared_template_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled_dir = Path(sys.executable).resolve().parent / "presentation" / "template"
        if bundled_dir.is_dir():
            return bundled_dir

    return Path(__file__).resolve().parents[1] / "template"


renderer = None
try:
    template_dir = _resolve_shared_template_dir()
    logger.debug(f"Shared statement template directory resolved to: {template_dir}")
    if template_dir.is_dir():
        renderer = StatementHtmlRenderer(template_dir=template_dir)
    else:
        logger.error(f"Template directory does not exist: {template_dir}")
except Exception as e:
    logger.exception(f"Failed to initialize statement renderer: {e}")
    renderer = None

def generate_learner_statement_html(main_window, acc_no, statement_settings):
    """Generates cumulative statement HTML for an individual learner using Jinja2."""
    logger.debug(f"Generating individual statement for acc_no: {acc_no} using Jinja2")
    if not renderer:
        return "<html><body><h2>Error</h2><p>Statement template engine not initialized.</p></body></html>"

    try:
        statement_service = StatementDocumentService(
            db_manager=main_window.db_manager,
            learner_repository=main_window.learner_repository,
            payment_repository=main_window.payment_repository,
            family_repository=main_window.family_repository
        )

        context_data = statement_service.get_learner_statement_data(acc_no, main_window.current_username)
        if not context_data:
            return f"<html><body><h2>Error</h2><p>Statement data not available for Acc No: {acc_no}.</p></body></html>"

        logo_path = statement_settings.get("logo_data") or statement_settings.get("logo_path") or getattr(main_window, "logo_path", "")
        html_output = renderer.render(context_data=context_data, statement_settings=statement_settings, logo_path=logo_path)
        logger.debug(f"Rendered HTML (first 500 chars): {html_output[:500]}...")
        return html_output

    except Exception as e:
        logger.exception(f"FATAL ERROR generating learner statement HTML for acc_no {acc_no} using Jinja2")
        return f"<html><body><h2>Internal Server Error</h2><p>An unexpected error occurred while generating the statement for Acc No: {acc_no}. Please contact support.</p></body></html>"

def generate_family_statement_html(main_window_instance, family_id, statement_settings):
    """Generates cumulative family statement HTML using Jinja2."""
    logger.debug(f"[Family {family_id}] Generating family statement using Jinja2...")
    if not renderer:
        return "<html><body><h2>Error</h2><p>Statement template engine not initialized.</p></body></html>"

    try:
        statement_service = StatementDocumentService(
            db_manager=main_window_instance.db_manager,
            learner_repository=main_window_instance.learner_repository,
            payment_repository=main_window_instance.payment_repository,
            family_repository=main_window_instance.family_repository
        )

        context_data = statement_service.get_family_statement_data(family_id, main_window_instance.current_username)
        if not context_data:
            return f"<html><body><h2>Error</h2><p>Statement data not available for Family ID: {family_id}.</p></body></html>"

        logo_path = statement_settings.get("logo_data") or statement_settings.get("logo_path") or getattr(main_window_instance, "logo_path", "")
        html_output = renderer.render(context_data=context_data, statement_settings=statement_settings, logo_path=logo_path)
        return html_output

    except Exception as e:
        logger.exception(f"FATAL ERROR generating family statement HTML for family_id {family_id}")
        return f"<html><body><h2>Error</h2><p>Could not generate statement for Family ID: {family_id}.</p></body></html>"
