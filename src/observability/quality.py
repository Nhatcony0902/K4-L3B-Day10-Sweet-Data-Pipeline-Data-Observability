from __future__ import annotations

from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROW_COUNT = 5
MAX_ROW_COUNT = 5000
MIN_SUMMARY_CHARS = 30
NOT_NULL_COLUMNS = ("paper_id", "title", "text_for_embedding")
MAX_STALE_RATIO = 0.25


def _build_expectations() -> list[gxe.Expectation]:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROW_COUNT, max_value=MAX_ROW_COUNT),
        *(gxe.ExpectColumnValuesToNotBeNull(column=column) for column in NOT_NULL_COLUMNS),
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
    ]


def _summarize_result(result: Any) -> dict[str, Any]:
    config = result.expectation_config
    details = result.result or {}
    return {
        "expectation": config.type,
        "column": config.kwargs.get("column"),
        "success": bool(result.success),
        "observed_value": details.get("observed_value"),
        "unexpected_count": details.get("unexpected_count"),
        "unexpected_percent": details.get("unexpected_percent"),
    }


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Tinh ty le bai bao cu (`age_days` > nguong); vuot `MAX_STALE_RATIO` thi `is_fresh=False`."""
    total_rows = len(df)
    published = pd.to_datetime(df["published"], errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum()) if total_rows else 0
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "latest_published": published.max().strftime("%Y-%m-%d") if published.notna().any() else None,
        "oldest_published": published.min().strftime("%Y-%m-%d") if published.notna().any() else None,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay Quality Gate GX 1.x (ephemeral context) + freshness, ghi `data/quality/<report_name>_quality_report.json`.

    `success` chi phan anh 4 nhom expectation cua GX; freshness la canh bao rieng qua `freshness.is_fresh`.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_papers_suite"))
    for expectation in _build_expectations():
        suite.add_expectation(expectation)
    validation = batch.validate(suite)

    checks = [_summarize_result(result) for result in validation.results]
    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "success": bool(validation.success),
        "row_count": len(df),
        "failed_checks": [check["expectation"] for check in checks if not check["success"]],
        "checks": checks,
        "freshness": evaluate_freshness_sla(df, settings),
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report va ghi JSON vao `report_path`."""
    payload = {"generated_at": now_utc().isoformat(), **evaluate_freshness_sla(df, settings)}
    write_json(report_path, payload)
    return payload
