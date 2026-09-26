from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from core.utils import clean_markup_text, compact_join
from ingestion.crossref import PaperRecord

DATE_FORMAT = "%Y-%m-%d"
REQUIRED_TEXT_COLUMNS = ("paper_id", "title", "summary")
CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "age_days",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
]


def _clean_list(values: object) -> list[str]:
    """Chuan hoa tung phan tu, bo phan tu rong va trung (giu thu tu)."""
    if not isinstance(values, (list, tuple)):
        return []
    cleaned = (clean_markup_text(value) for value in values)
    return list(dict.fromkeys(value for value in cleaned if value))


def build_text_for_embedding(row: pd.Series) -> str:
    """Ghep 5 phan ngu canh de embed: Title / Authors / Published / Categories / Summary."""
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Loai dong thieu paper_id/title/summary hoac ngay xuat ban khong hop le;
    trung `paper_id` thi giu ban co `updated` moi nhat.
    """
    df = pd.DataFrame([asdict(record) for record in records], columns=CLEAN_COLUMNS[:11])

    df["paper_id"] = df["paper_id"].map(clean_markup_text).str.lower()
    for column in ("title", "summary", "primary_category", "abs_url", "pdf_url", "comment"):
        df[column] = df[column].map(clean_markup_text)
    df["authors"] = df["authors"].map(_clean_list)
    df["categories"] = df["categories"].map(_clean_list)
    df["primary_category"] = [
        primary or (categories[0] if categories else "")
        for primary, categories in zip(df["primary_category"], df["categories"], strict=True)
    ]

    published = pd.to_datetime(df["published"], errors="coerce")
    updated = pd.to_datetime(df["updated"], errors="coerce").fillna(published)
    has_required_text = df[list(REQUIRED_TEXT_COLUMNS)].ne("").all(axis=1)
    keep = has_required_text & published.notna()
    df, published, updated = df[keep].copy(), published[keep], updated[keep]

    df["published"] = published.dt.strftime(DATE_FORMAT)
    df["updated"] = updated.dt.strftime(DATE_FORMAT)
    df["age_days"] = (pd.Timestamp(run_date.date()) - published).dt.days.astype(int)
    df["authors_joined"] = df["authors"].map(compact_join)
    df["categories_joined"] = df["categories"].map(compact_join)
    df["summary_chars"] = df["summary"].str.len().astype(int)
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1) if not df.empty else pd.Series(dtype=str)

    df = (
        df.sort_values(["paper_id", "updated"], ascending=[True, False])
        .drop_duplicates(subset="paper_id", keep="first")
        .sort_values(["published", "paper_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return df[CLEAN_COLUMNS]
