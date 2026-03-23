from __future__ import annotations

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader


class StatementHtmlRenderer:
    def __init__(self, template_dir: Optional[Path] = None) -> None:
        self.src_root = Path(__file__).resolve().parents[2]

        template_paths = []
        if template_dir is not None:
            template_paths.append(str(template_dir))
        template_paths.append(str(self.src_root / "presentation" / "template"))

        self.jinja = Environment(loader=FileSystemLoader(template_paths), autoescape=True)
        self.statement_style = self._load_statement_style()

    def _load_statement_style(self) -> str:
        try:
            from presentation.styles.styles import get_statement_style

            return get_statement_style()
        except Exception:
            style_path = self.src_root / "presentation" / "styles" / "styles.css"
            if style_path.exists():
                return style_path.read_text(encoding="utf-8")
            return (
                "body{font-family:Arial,sans-serif;margin:20px;} "
                "table{width:100%;border-collapse:collapse;} "
                "th,td{border:1px solid #ddd;padding:6px;}"
            )

    def _resolve_logo_src(self, raw_path: str) -> str:
        cleaned = str(raw_path or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith(("data:", "http://", "https://", "file://")):
            return cleaned

        logo_path = Path(cleaned).expanduser()
        repo_root = self.src_root.parent
        candidates = []
        if logo_path.is_absolute():
            candidates.append(logo_path)
        else:
            candidates.append((self.src_root / logo_path).resolve())
            candidates.append((repo_root / logo_path).resolve())
            candidates.append((Path.cwd() / logo_path).resolve())
            candidates.append(logo_path.resolve())

        resolved = next((candidate for candidate in candidates if candidate.exists() and candidate.is_file()), None)
        if resolved is None:
            return ""

        mime_type, _ = mimetypes.guess_type(str(resolved))
        payload = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return f"data:{mime_type or 'image/png'};base64,{payload}"

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = str(value or "").strip()
        if text.lower() in {"n/a", "none", "null"}:
            return ""
        return text

    @classmethod
    def _build_company_contact(cls, phone: Any, whatsapp: Any, email: Any) -> str:
        parts = []

        cleaned_phone = cls._clean_text(phone)
        cleaned_whatsapp = cls._clean_text(whatsapp)
        cleaned_email = cls._clean_text(email)

        if cleaned_phone:
            parts.append(f"Phone: {cleaned_phone}")
        if cleaned_whatsapp:
            parts.append(f"WhatsApp: {cleaned_whatsapp}")
        if cleaned_email:
            parts.append(cleaned_email)

        return " | ".join(parts)

    @staticmethod
    def _statement_period_label(context_data: Dict[str, Any]) -> str:
        label = str(context_data.get("statement_period_label") or "").strip()
        if label:
            return label

        semester_name = str(context_data.get("semester_name") or "").strip()
        semester_year = context_data.get("semester_year")
        if semester_name and semester_year:
            return f"{semester_name} {semester_year}"

        return datetime.now().strftime("%B %Y")

    def render(
        self,
        context_data: Dict[str, Any],
        statement_settings: Dict[str, Any],
        logo_path: Optional[str] = None,
    ) -> str:
        template = self.jinja.get_template("statement_template.html")

        context = {
            "statement_style": self.statement_style,
            "logo_src": self._resolve_logo_src(
                str(logo_path or statement_settings.get("logo_data") or statement_settings.get("logo_path") or "")
            ),
            "company_address": statement_settings.get("address", ""),
            "thank_you_message": statement_settings.get("thank_you_message", ""),
            "statement_message": statement_settings.get("statement_message", ""),
            "email_contact": statement_settings.get("email", ""),
            "bank_name": statement_settings.get("bank_name", ""),
            "account_holder": statement_settings.get("account_holder", ""),
            "account_number": statement_settings.get("account_number", ""),
            "statement_period_label": self._statement_period_label(context_data),
            **context_data,
        }

        context["company_address"] = self._clean_text(context.get("company_address"))
        context["statement_message"] = self._clean_text(context.get("statement_message"))
        context["thank_you_message"] = self._clean_text(context.get("thank_you_message"))
        context["email_contact"] = self._clean_text(context.get("email_contact"))
        context["bank_name"] = self._clean_text(context.get("bank_name"))
        context["account_holder"] = self._clean_text(context.get("account_holder"))
        context["account_number"] = self._clean_text(context.get("account_number"))
        context["payment_reference"] = self._clean_text(context.get("payment_reference"))
        context["company_contact"] = self._build_company_contact(
            statement_settings.get("phone", ""),
            statement_settings.get("whatsapp", ""),
            context.get("email_contact", ""),
        )

        return template.render(context)
