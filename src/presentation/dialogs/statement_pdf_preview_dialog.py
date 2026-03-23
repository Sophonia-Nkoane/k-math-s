from __future__ import annotations

from pathlib import Path
import tempfile

from PySide6.QtCore import QMargins
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QHBoxLayout, QLabel

from presentation.components.buttons import ButtonFactory
from presentation.components.window_component import WindowComponent
from presentation.styles.colors import TEXT_COLOR


class StatementPdfPreviewDialog(WindowComponent):
    def __init__(self, pdf_bytes: bytes, parent=None, title: str = "Statement Preview"):
        super().__init__(parent=parent, title=title, size=(980, 740))
        self._temp_pdf_path: Path | None = None
        self._pdf_document = QPdfDocument(self)
        self._pdf_view = QPdfView(self)
        self._zoom_label = QLabel()
        self._page_label = QLabel()

        self._load_pdf_document(pdf_bytes)
        self._build_ui()

    def _load_pdf_document(self, pdf_bytes: bytes) -> None:
        if not pdf_bytes:
            raise RuntimeError("No statement PDF data available for preview.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
            handle.write(pdf_bytes)
            self._temp_pdf_path = Path(handle.name)

        load_error = self._pdf_document.load(str(self._temp_pdf_path))
        if load_error != QPdfDocument.Error.None_:
            self._cleanup_temp_file()
            raise RuntimeError(f"Failed to load statement PDF for preview: {load_error.name}.")

    def _build_ui(self) -> None:
        zoom_out_button = ButtonFactory.create_view_button("Zoom -")
        actual_size_button = ButtonFactory.create_view_button("100%")
        zoom_in_button = ButtonFactory.create_view_button("Zoom +")
        fit_width_button = ButtonFactory.create_view_button("Fit Width")
        fit_page_button = ButtonFactory.create_view_button("Fit Page")
        close_button = ButtonFactory.create_close_button("Close")

        zoom_out_button.clicked.connect(self._zoom_out)
        actual_size_button.clicked.connect(self._set_actual_size)
        zoom_in_button.clicked.connect(self._zoom_in)
        fit_width_button.clicked.connect(self._set_fit_width)
        fit_page_button.clicked.connect(self._set_fit_page)
        close_button.clicked.connect(self.reject)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(zoom_out_button)
        toolbar_layout.addWidget(actual_size_button)
        toolbar_layout.addWidget(zoom_in_button)
        toolbar_layout.addWidget(fit_width_button)
        toolbar_layout.addWidget(fit_page_button)
        toolbar_layout.addStretch()

        for label in (self._zoom_label, self._page_label):
            label.setStyleSheet(f"color: {TEXT_COLOR()}; font-weight: 600;")

        toolbar_layout.addWidget(self._zoom_label)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(self._page_label)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(close_button)

        self._pdf_view.setDocument(self._pdf_document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        if hasattr(self._pdf_view, "setPageSpacing"):
            self._pdf_view.setPageSpacing(12)
        if hasattr(self._pdf_view, "setDocumentMargins"):
            self._pdf_view.setDocumentMargins(QMargins(12, 12, 12, 12))

        self.add_layout(toolbar_layout)
        self.add_widget(self._pdf_view)
        self._page_label.setText(f"Pages: {self._pdf_document.pageCount()}")
        self._update_zoom_label()

    def _set_fit_width(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._update_zoom_label()

    def _set_fit_page(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._update_zoom_label()

    def _set_actual_size(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(1.0)
        self._update_zoom_label()

    def _zoom_in(self) -> None:
        current_zoom = self._pdf_view.zoomFactor()
        if self._pdf_view.zoomMode() != QPdfView.ZoomMode.Custom:
            current_zoom = 1.0
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(min(current_zoom * 1.2, 5.0))
        self._update_zoom_label()

    def _zoom_out(self) -> None:
        current_zoom = self._pdf_view.zoomFactor()
        if self._pdf_view.zoomMode() != QPdfView.ZoomMode.Custom:
            current_zoom = 1.0
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(max(current_zoom / 1.2, 0.35))
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        zoom_mode = self._pdf_view.zoomMode()
        if zoom_mode == QPdfView.ZoomMode.FitToWidth:
            self._zoom_label.setText("Zoom: Fit Width")
            return
        if zoom_mode == QPdfView.ZoomMode.FitInView:
            self._zoom_label.setText("Zoom: Fit Page")
            return
        zoom_percent = round(self._pdf_view.zoomFactor() * 100)
        self._zoom_label.setText(f"Zoom: {zoom_percent}%")

    def reject(self) -> None:
        self._cleanup_temp_file()
        super().reject()

    def _cleanup_temp_file(self) -> None:
        try:
            self._pdf_document.close()
        except Exception:
            pass

        if not self._temp_pdf_path:
            return

        try:
            self._temp_pdf_path.unlink(missing_ok=True)
        except TypeError:
            if self._temp_pdf_path.exists():
                self._temp_pdf_path.unlink()
        finally:
            self._temp_pdf_path = None
