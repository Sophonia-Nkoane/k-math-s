from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path

from PySide6.QtCore import QEventLoop, QMarginsF, QRect, QUrl
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWebEngineCore import QWebEnginePage


def _configure_qt_webengine_environment() -> None:
    try:
        import PySide6
    except Exception:
        return

    qt_dir = Path(PySide6.__file__).resolve().parent / "Qt"
    plugin_dir = qt_dir / "plugins"
    resources_dir = qt_dir / "resources"
    locales_dir = qt_dir / "translations" / "qtwebengine_locales"
    process_path = qt_dir / "libexec" / "QtWebEngineProcess"

    if plugin_dir.exists():
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugin_dir))
        if str(plugin_dir) not in QApplication.libraryPaths():
            QApplication.addLibraryPath(str(plugin_dir))
    if resources_dir.exists():
        os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", str(resources_dir))
    if locales_dir.exists():
        os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", str(locales_dir))
    if process_path.exists():
        os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(process_path))


def build_statement_pdf_bytes(html: str) -> bytes:
    if not html:
        raise RuntimeError("Statement HTML not generated.")

    _configure_qt_webengine_environment()

    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication([])
        created_app = True

    page = QWebEnginePage()
    base_url = QUrl.fromLocalFile(str(Path.cwd()) + "/")
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(5.08, 7.62, 5.08, 7.62),
        QPageLayout.Unit.Millimeter,
    )

    load_loop = QEventLoop()
    pdf_loop = QEventLoop()
    result: dict[str, bytes | str] = {}

    def handle_load(ok: bool) -> None:
        if not ok:
            result["error"] = "Failed to load statement HTML for PDF generation."
        load_loop.quit()

    def handle_pdf(pdf_data) -> None:
        result["pdf"] = bytes(pdf_data)
        pdf_loop.quit()

    page.loadFinished.connect(handle_load)
    page.setHtml(html, base_url)
    load_loop.exec()

    if "error" in result:
        if created_app:
            app.quit()
        raise RuntimeError(str(result["error"]))

    page.printToPdf(handle_pdf, pageLayout=page_layout)
    pdf_loop.exec()

    if created_app:
        app.quit()

    pdf_bytes = result.get("pdf", b"")
    if not pdf_bytes:
        raise RuntimeError("Desktop PDF generation returned no data.")
    return bytes(pdf_bytes)


def save_statement_pdf_bytes(pdf_bytes: bytes, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)


def render_statement_pdf_bytes_to_printer(pdf_bytes: bytes, printer: QPrinter) -> None:
    render_statement_pdf_documents_to_printer([pdf_bytes], printer)


def render_statement_pdf_documents_to_printer(pdf_documents: Iterable[bytes], printer: QPrinter) -> None:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "PyMuPDF is required for statement preview and printing. Install dependency first."
        ) from exc

    documents = [pdf for pdf in pdf_documents if pdf]
    if not documents:
        raise RuntimeError("No statement PDF data available.")

    painter = QPainter(printer)
    if not painter.isActive():
        raise RuntimeError("Could not initialise the printer for statement output.")

    rendered_any_page = False
    try:
        for pdf_bytes in documents:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                for page_index in range(pdf_document.page_count):
                    if rendered_any_page:
                        printer.newPage()

                    page = pdf_document.load_page(page_index)
                    target_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    page_rect = page.rect

                    if page_rect.width <= 0 or page_rect.height <= 0:
                        raise RuntimeError(f"Invalid PDF page size on page {page_index + 1}.")
                    if target_rect.width() <= 0 or target_rect.height() <= 0:
                        raise RuntimeError("The selected printer does not expose a printable page area.")

                    scale = min(
                        target_rect.width() / float(page_rect.width),
                        target_rect.height() / float(page_rect.height),
                    )
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    image = _pixmap_to_qimage(pixmap)

                    x = target_rect.x() + max(0, (target_rect.width() - image.width()) // 2)
                    y = target_rect.y() + max(0, (target_rect.height() - image.height()) // 2)
                    painter.drawImage(QRect(x, y, image.width(), image.height()), image)
                    rendered_any_page = True
            finally:
                pdf_document.close()
    finally:
        painter.end()

    if not rendered_any_page:
        raise RuntimeError("The generated statement PDF contained no printable pages.")


def _pixmap_to_qimage(pixmap) -> QImage:
    image_format = QImage.Format.Format_RGBA8888 if pixmap.alpha else QImage.Format.Format_RGB888
    return QImage(
        pixmap.samples,
        pixmap.width,
        pixmap.height,
        pixmap.stride,
        image_format,
    ).copy()
