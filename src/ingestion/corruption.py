from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import DATE_FORMAT, build_text_for_embedding

SEED = 42
DROP_LATEST_RATIO = 0.20
# Ty le (tren so dong con lai sau khi drop) cho tung loai loi; cac nhom dong khong giao nhau.
ROW_RATIOS = {
    "blank_summary": 0.15,
    "inject_noise": 0.15,
    "truncate_title": 0.15,
    "stale_date": 0.20,
    "duplicate_rows": 0.10,
}
NOISE_TOKENS = ("#@!$%^&*", "lorem_ipsum_xyz", "NULL", "<<<ERR>>>", "0xDEADBEEF", "????")
TRUNCATED_TITLE_CHARS = 7
STALE_SHIFT_DAYS = 365


def _count(total: int, ratio: float) -> int:
    return max(1, math.ceil(total * ratio)) if total else 0


def _log(corruption: str, paper_id: str, field: str | None, before: Any, after: Any) -> dict[str, Any]:
    return {"corruption": corruption, "paper_id": paper_id, "field": field, "before": before, "after": after}


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Tiem 6 dang loi du lieu (tai lap duoc voi SEED) va ghi nhat ky tung dong bi bien doi."""
    rng = np.random.default_rng(SEED)
    entries: list[dict[str, Any]] = []
    corrupted = df.copy()
    corrupted["published"] = pd.to_datetime(corrupted["published"]).dt.strftime(DATE_FORMAT)

    # 1. Drop latest records: bo 20% bai moi nhat.
    drop_count = math.ceil(len(corrupted) * DROP_LATEST_RATIO)
    latest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_count)
    for _, row in latest.iterrows():
        entries.append(_log("drop_latest_records", row["paper_id"], None, row["published"], "dropped"))
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)

    # Chia cac dong con lai thanh nhom rieng cho tung loai loi.
    shuffled = list(rng.permutation(len(corrupted)))
    groups: dict[str, list[int]] = {}
    for name, ratio in ROW_RATIOS.items():
        size = _count(len(corrupted), ratio)
        groups[name], shuffled = shuffled[:size], shuffled[size:]

    # 2. Blank summary.
    for i in groups["blank_summary"]:
        before = corrupted.at[i, "summary"]
        corrupted.at[i, "summary"] = ""
        entries.append(_log("blank_summary", corrupted.at[i, "paper_id"], "summary", before, ""))

    # 3. Inject noise: chen chuoi rac vao dau, giua va cuoi tom tat.
    for i in groups["inject_noise"]:
        before = corrupted.at[i, "summary"]
        words = before.split()
        tokens = rng.choice(NOISE_TOKENS, size=3, replace=False)
        middle = len(words) // 2
        after = " ".join([tokens[0], *words[:middle], tokens[1], *words[middle:], tokens[2]])
        corrupted.at[i, "summary"] = after
        entries.append(_log("inject_noise", corrupted.at[i, "paper_id"], "summary", before, after))

    # 4. Truncate title xuong duoi 8 ky tu.
    for i in groups["truncate_title"]:
        before = corrupted.at[i, "title"]
        after = before[:TRUNCATED_TITLE_CHARS]
        corrupted.at[i, "title"] = after
        entries.append(_log("truncate_title", corrupted.at[i, "paper_id"], "title", before, after))

    # 5. Stale date: lui ngay xuat ban 365 ngay.
    for i in groups["stale_date"]:
        before = corrupted.at[i, "published"]
        after = (pd.Timestamp(before) - pd.Timedelta(days=STALE_SHIFT_DAYS)).strftime(DATE_FORMAT)
        corrupted.at[i, "published"] = after
        corrupted.at[i, "updated"] = after
        corrupted.at[i, "age_days"] = int(corrupted.at[i, "age_days"]) + STALE_SHIFT_DAYS
        entries.append(_log("stale_date", corrupted.at[i, "paper_id"], "published", before, after))

    # 7. Rebuild cac cot phat sinh truoc khi nhan ban de ban sao giong het ban goc.
    corrupted["summary_chars"] = corrupted["summary"].str.len().astype(int)
    corrupted["text_for_embedding"] = corrupted.apply(build_text_for_embedding, axis=1)

    # 6. Duplicate rows.
    duplicates = corrupted.loc[groups["duplicate_rows"]]
    for _, row in duplicates.iterrows():
        entries.append(_log("duplicate_rows", row["paper_id"], None, 1, 2))
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["corruption"]] = counts.get(entry["corruption"], 0) + 1
    write_json(
        Path(output_log_path),
        {
            "generated_at": now_utc().isoformat(),
            "seed": SEED,
            "input_rows": len(df),
            "output_rows": len(corrupted),
            "corruption_counts": counts,
            "entries": entries,
        },
    )
    return corrupted
