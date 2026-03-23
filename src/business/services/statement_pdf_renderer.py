from __future__ import annotations

import ctypes
import os
from pathlib import Path


def _preload_linux_text_libs() -> None:
    if os.name != "posix":
        return

    candidate_paths = [
        "/lib/x86_64-linux-gnu/libharfbuzz.so.0",
        "/lib/x86_64-linux-gnu/libfontconfig.so.1",
        "/lib/x86_64-linux-gnu/libgobject-2.0.so.0",
        "/lib/x86_64-linux-gnu/libpango-1.0.so.0",
        "/lib/x86_64-linux-gnu/libpangocairo-1.0.so.0",
        "/lib/x86_64-linux-gnu/libpangoft2-1.0.so.0",
        "/lib/x86_64-linux-gnu/libcairo.so.2",
        "/lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0",
        "/usr/lib/x86_64-linux-gnu/libharfbuzz.so.0",
        "/usr/lib/x86_64-linux-gnu/libfontconfig.so.1",
        "/usr/lib/x86_64-linux-gnu/libgobject-2.0.so.0",
        "/usr/lib/x86_64-linux-gnu/libpango-1.0.so.0",
        "/usr/lib/x86_64-linux-gnu/libpangocairo-1.0.so.0",
        "/usr/lib/x86_64-linux-gnu/libpangoft2-1.0.so.0",
        "/usr/lib/x86_64-linux-gnu/libcairo.so.2",
        "/usr/lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0",
    ]

    for path in candidate_paths:
        if not os.path.exists(path):
            continue
        try:
            ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
        except OSError:
            continue


def render_statement_pdf_bytes(html: str) -> bytes:
    try:
        _preload_linux_text_libs()
        from weasyprint import HTML  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "weasyprint is required for HTML-to-PDF rendering. Install dependency first."
        ) from exc

    return HTML(string=html).write_pdf()


def write_statement_pdf_bytes(pdf_bytes: bytes, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return path
