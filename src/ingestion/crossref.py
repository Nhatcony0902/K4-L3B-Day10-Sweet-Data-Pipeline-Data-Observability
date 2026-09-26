from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import clean_markup_text, normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
REQUEST_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "day10-data-observability-lab/0.1 (educational data pipeline)"
DATE_FIELDS_BY_PRIORITY = ("published", "published-print", "published-online", "issued", "created")
UPDATED_DATE_FIELDS_BY_PRIORITY = ("updated", "created")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _first_text(value: Any) -> str:
    """Crossref tra `title` dang list; lay phan tu dau tien khong rong."""
    if isinstance(value, list):
        return next((text for text in map(clean_markup_text, value) if text), "")
    return clean_markup_text(value)


def _parse_authors(raw_authors: Any) -> list[str]:
    authors: list[str] = []
    for author in raw_authors or []:
        if not isinstance(author, dict):
            continue
        # Tac gia to chuc chi co truong `name`, khong co given/family.
        full_name = clean_markup_text(f"{author.get('given', '')} {author.get('family', '')}") or clean_markup_text(
            author.get("name")
        )
        if full_name:
            authors.append(full_name)
    return authors


def _parse_categories(raw_subjects: Any) -> list[str]:
    categories: list[str] = []
    for subject in raw_subjects or []:
        cleaned = clean_markup_text(subject)
        if cleaned and cleaned not in categories:
            categories.append(cleaned)
    return categories


def _date_from_field(field: Any) -> str:
    """Doc `date-parts` (co the thieu thang/ngay) hoac `date-time`, tra ve YYYY-MM-DD."""
    if not isinstance(field, dict):
        return ""
    parts = (field.get("date-parts") or [[]])[0] or []
    if parts and parts[0]:
        year, month, day = (list(parts) + [1, 1])[:3]
        return f"{int(year):04d}-{int(month or 1):02d}-{int(day or 1):02d}"
    date_time = field.get("date-time")
    return date_time[:10] if isinstance(date_time, str) else ""


def _first_date(item: dict, field_names: tuple[str, ...]) -> str:
    return next((date for date in (_date_from_field(item.get(name)) for name in field_names) if date), "")


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if isinstance(link, dict) and link.get("content-type") == "application/pdf" and link.get("URL"):
            return link["URL"]
    return fallback


def _parse_item(item: dict) -> PaperRecord | None:
    doi = normalize_whitespace(str(item.get("DOI") or "")).lower()
    title = _first_text(item.get("title"))
    summary = clean_markup_text(item.get("abstract"))
    published = _first_date(item, DATE_FIELDS_BY_PRIORITY)
    if not (doi and title and summary and published):
        return None

    categories = _parse_categories(item.get("subject"))
    abs_url = item.get("URL") or f"https://doi.org/{doi}"
    return PaperRecord(
        paper_id=doi,
        title=title,
        summary=summary,
        authors=_parse_authors(item.get("author")),
        categories=categories,
        primary_category=categories[0] if categories else "",
        published=published,
        updated=_first_date(item, UPDATED_DATE_FIELDS_BY_PRIORITY) or published,
        abs_url=abs_url,
        pdf_url=_pdf_url(item, abs_url),
        comment=f"Crossref record {doi}",
    )


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref `/works` payload thanh list `PaperRecord`.

    Record thieu DOI/title/abstract/ngay xuat ban bi loai; DOI trung chi giu ban dau tien.
    """
    items = (payload.get("message") or {}).get("items") or []
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    skipped = 0
    for item in items:
        record = _parse_item(item) if isinstance(item, dict) else None
        if record is None or record.paper_id in seen_ids:
            skipped += 1
            continue
        seen_ids.add(record.paper_id)
        records.append(record)
    if skipped:
        logger.warning("Bo qua %d/%d Crossref item khong hop le hoac trung DOI.", skipped, len(items))
    return records


def _request_crossref(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response.json()
            last_error = requests.HTTPError(f"HTTP {response.status_code}", response=response)
            retry_after = response.headers.get("Retry-After", "")
            wait_seconds = float(retry_after) if retry_after.isdigit() else BACKOFF_BASE_SECONDS**attempt
        except (requests.ConnectionError, requests.Timeout) as error:
            last_error = error
            wait_seconds = BACKOFF_BASE_SECONDS**attempt
        logger.warning("Crossref attempt %d/%d that bai: %s", attempt, MAX_ATTEMPTS, last_error)
        if attempt < MAX_ATTEMPTS:
            time.sleep(wait_seconds)
    raise RuntimeError(f"Crossref API khong phan hoi sau {MAX_ATTEMPTS} lan thu: {last_error}")


def _fetch_live_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API; loi mang/429/5xx thi fallback doc snapshot local."""
    raw_response_path = settings.paths.raw_api_response
    try:
        payload = _request_crossref(settings)
        records = parse_crossref_payload(payload)
        if not records:
            raise RuntimeError("Crossref API tra ve 0 record hop le.")
        write_json(raw_response_path, payload)
        logger.info("Da tai %d record tu %s.", len(records), settings.source_api)
        return records
    except (RuntimeError, requests.RequestException, ValueError) as error:
        if not raw_response_path.exists():
            raise RuntimeError(
                f"Khong goi duoc Crossref API va khong co snapshot tai {raw_response_path}."
            ) from error
        logger.warning("Crossref API loi (%s) -> fallback snapshot %s.", error, raw_response_path)
        return parse_crossref_payload(read_json(raw_response_path))


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay raw records va luu `crossref_records.json`.

    Mac dinh doc snapshot `crossref_response.json` de ket qua on dinh, tai lap duoc
    (API song hien khong tra `subject` -> mat categories). Dat `REFRESH_SOURCE=1`
    de goi Crossref API that (co retry + fallback snapshot).
    """
    raw_response_path = settings.paths.raw_api_response
    if settings.refresh_source or not raw_response_path.exists():
        records = _fetch_live_records(settings)
    else:
        logger.info("REFRESH_SOURCE tat -> dung snapshot %s.", raw_response_path)
        records = parse_crossref_payload(read_json(raw_response_path))

    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot `crossref_records.json` va map thanh `PaperRecord`."""
    return [PaperRecord(**item) for item in read_json(path)]
