from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter


STATEMENT_PAGE_SIZE = QPageSize(QPageSize.PageSizeId.A4)
STATEMENT_MARGINS_MM = QMarginsF(5.08, 7.62, 5.08, 7.62)


def configure_statement_printer(printer: QPrinter) -> None:
    try:
        printer.setPageSize(STATEMENT_PAGE_SIZE)
    except Exception:
        pass

    try:
        printer.setPageMargins(STATEMENT_MARGINS_MM, QPageLayout.Unit.Millimeter)
    except Exception:
        pass


def build_statement_document(html: str, printer: QPrinter | None = None) -> QTextDocument:
    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setHtml(html)

    if printer is not None:
        try:
            page_rect = printer.pageRect(QPrinter.Unit.Point)
            document.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
        except Exception:
            pass

    return document


def print_statement_html_to_printer(html: str, printer: QPrinter) -> None:
    if not html:
        raise RuntimeError("Statement HTML not generated.")

    configure_statement_printer(printer)
    document = build_statement_document(html, printer)
    document.print_(printer)


def print_statement_html_documents_to_printer(html_documents: Iterable[str], printer: QPrinter) -> None:
    configure_statement_printer(printer)

    rendered_any = False
    for html in html_documents:
        if not html:
            continue

        if rendered_any:
            printer.newPage()

        document = build_statement_document(html, printer)
        document.print_(printer)
        rendered_any = True

    if not rendered_any:
        raise RuntimeError("No statements were available to print.")


def save_statement_html_to_pdf(html: str, output_path: str | Path) -> Path:
    if not html:
        raise RuntimeError("Statement HTML not generated.")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    configure_statement_printer(printer)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    print_statement_html_to_printer(html, printer)
    return path
