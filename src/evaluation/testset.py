from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json

TEST_SET_SIZE = 10
QUESTION_TYPES = ("summary", "authors", "date", "categories")
REQUIRED_COLUMNS = ("paper_id", "title", "summary", "authors", "categories", "published")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _question_row(question_type: str, paper: pd.Series) -> dict[str, Any]:
    title = normalize_whitespace(str(paper["title"]))
    if question_type == "summary":
        question = f"What is the summary of the paper '{title}'?"
        ground_truth = first_sentence(str(paper["summary"]))
    elif question_type == "authors":
        question = f"Who authored the paper '{title}'?"
        ground_truth = ", ".join(_as_list(paper["authors"]))
    elif question_type == "date":
        question = f"When was the paper '{title}' published?"
        ground_truth = str(paper["published"])[:10]
    else:
        question = f"What categories does the paper '{title}' belong to?"
        ground_truth = ", ".join(_as_list(paper["categories"]))
    return {
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": [str(paper["paper_id"])],
    }


def _is_usable(question_type: str, paper: pd.Series) -> bool:
    if question_type == "summary":
        return bool(first_sentence(str(paper["summary"] or "")))
    if question_type == "authors":
        return bool(_as_list(paper["authors"]))
    if question_type == "date":
        return bool(str(paper["published"] or "").strip())
    return bool(_as_list(paper["categories"]))


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set (10 cau hoi, chia deu 4 dang) tu cleaned dataframe va ghi ra JSON."""
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Cleaned dataframe is missing columns: {missing}")

    papers = (
        df.dropna(subset=["paper_id", "title"])
        .drop_duplicates(subset="paper_id")
        .sort_values(["published", "paper_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    if len(papers) < TEST_SET_SIZE:
        raise ValueError(f"Need at least {TEST_SET_SIZE} documents to build the test set, got {len(papers)}.")

    # Round-robin qua 4 dang -> phan bo 3/3/2/2; moi cau hoi dung mot paper khac nhau.
    rows: list[dict[str, Any]] = []
    candidates = papers.iterrows()
    for index in range(TEST_SET_SIZE):
        question_type = QUESTION_TYPES[index % len(QUESTION_TYPES)]
        for _, paper in candidates:
            if _is_usable(question_type, paper):
                rows.append(_question_row(question_type, paper))
                break
        else:
            raise ValueError(f"Not enough usable documents to build a '{question_type}' question.")

    test_set = [{"id": f"eval_{i:03d}", **row} for i, row in enumerate(rows, start=1)]
    write_json(Path(output_path), test_set)
    return test_set
