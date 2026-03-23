from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple


ALLOWED_PAGE_SIZES: Tuple[int, ...] = (10, 25, 50, 100)


def normalize_page_params(page: int | None, page_size: int | None) -> Tuple[int, int]:
    clean_page = int(page or 1)
    clean_page_size = int(page_size or 25)
    if clean_page < 1:
        clean_page = 1
    if clean_page_size not in ALLOWED_PAGE_SIZES:
        clean_page_size = 25
    return clean_page, clean_page_size


def _sort_key(value: Any) -> Any:
    if value is None:
        return (2, "")
    if isinstance(value, (int, float)):
        return (0, value)
    text = str(value).strip()
    if not text:
        return (2, "")
    try:
        numeric = float(text)
        return (0, numeric)
    except ValueError:
        return (1, text.lower())


def sort_rows(rows: Sequence[Dict[str, Any]], sort_by: str, sort_dir: str = "asc") -> List[Dict[str, Any]]:
    reverse = str(sort_dir).lower() == "desc"
    return sorted(rows, key=lambda item: _sort_key(item.get(sort_by)), reverse=reverse)


def paginate_rows(rows: Sequence[Dict[str, Any]], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int, int]:
    clean_page, clean_page_size = normalize_page_params(page, page_size)
    total_count = len(rows)
    total_pages = max(1, math.ceil(total_count / clean_page_size)) if total_count else 1
    if clean_page > total_pages:
        clean_page = total_pages
    start = (clean_page - 1) * clean_page_size
    end = start + clean_page_size
    return list(rows[start:end]), total_count, total_pages


def sort_and_paginate(
    rows: Sequence[Dict[str, Any]],
    sort_by: str,
    sort_dir: str,
    page: int,
    page_size: int,
) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
    clean_page, clean_page_size = normalize_page_params(page, page_size)
    sorted_rows = sort_rows(rows, sort_by=sort_by, sort_dir=sort_dir)
    items, total_count, total_pages = paginate_rows(sorted_rows, page=clean_page, page_size=clean_page_size)
    if total_count:
        max_page = max(1, total_pages)
        clean_page = min(clean_page, max_page)
    return items, total_count, total_pages, clean_page, clean_page_size

