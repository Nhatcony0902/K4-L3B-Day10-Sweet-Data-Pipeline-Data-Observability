from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation import evaluate_pipeline
from ingestion import build_clean_dataframe, corrupt_clean_dataframe, load_raw_records, parse_crossref_payload
from observability import evaluate_freshness_sla, generate_corruption_report, run_data_quality_checks
from observability.reporting import format_comparison_table
from retrieval import LocalEmbeddingIndex

logger = logging.getLogger(__name__)


def _require(path, hint: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. {hint}")


def _save_dataset(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _evaluate_state(settings: Settings, df: pd.DataFrame, embeddings_path, metrics_path, answers_path):
    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=embeddings_path)
    return evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Idempotent repair: dung lai dataset sach tu raw snapshot bat bien bang chinh logic clean cua pipeline.

    Chay lai bao nhieu lan cung cho cung mot tap dong va ghi de artifact repaired.
    """
    if settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        _require(settings.paths.raw_api_response, "No raw snapshot available for repair.")
        records = parse_crossref_payload(read_json(settings.paths.raw_api_response))
    repaired = build_clean_dataframe(records, run_date=now_utc())
    _save_dataset(repaired, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    return repaired


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Corrupt -> evaluate (silent failure) -> repair tu raw snapshot -> re-evaluate -> bao cao 3 trang thai."""
    hint = "Run `python script/run_phase1.py` first."
    for path in (settings.paths.clean_json, settings.paths.eval_testset, settings.paths.baseline_metrics):
        _require(path, hint)

    # 1. Baseline
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_answers = read_json(settings.paths.baseline_answers) if settings.paths.baseline_answers.exists() else []
    baseline_quality = (
        read_json(settings.paths.baseline_quality_report) if settings.paths.baseline_quality_report.exists() else None
    )
    clean_df = pd.read_json(settings.paths.clean_json, dtype={"paper_id": str, "published": str, "updated": str})

    # 2. Corrupted: tiem loi -> luu -> index + evaluate -> quality gate
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    _save_dataset(corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json)
    corrupted = _evaluate_state(
        settings,
        corrupted_df,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")

    # 3. Repaired: khoi phuc tu raw snapshot -> index + evaluate -> quality gate
    repaired_df = repair_from_raw_snapshot(settings)
    repaired = _evaluate_state(
        settings,
        repaired_df,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")

    # 4. Bao cao doi chieu
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted.summary,
        repaired_metrics=repaired.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=evaluate_freshness_sla(corrupted_df, settings),
        repaired_freshness=evaluate_freshness_sla(repaired_df, settings),
        baseline_quality=baseline_quality,
        corruption_log=read_json(settings.paths.corruption_log),
        answers_by_state={"Baseline": baseline_answers, "Corrupted": corrupted.answers, "Repaired": repaired.answers},
    )
    return {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted.summary,
        "repaired_metrics": repaired.summary,
        "corrupted_quality_success": corrupted_quality["success"],
        "repaired_quality_success": repaired_quality["success"],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    result = run_corruption_flow_pipeline(settings)
    print()
    print(format_comparison_table(result["baseline_metrics"], result["corrupted_metrics"], result["repaired_metrics"]))
    print()
    print(
        f"Quality gate: Corrupted={'PASS' if result['corrupted_quality_success'] else 'FAIL'} | "
        f"Repaired={'PASS' if result['repaired_quality_success'] else 'FAIL'}"
    )
    print(f"Report: {settings.paths.comparison_report}")
