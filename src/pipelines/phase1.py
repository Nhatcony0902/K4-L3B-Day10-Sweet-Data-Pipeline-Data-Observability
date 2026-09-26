from __future__ import annotations

import logging
from typing import Any

from core.config import Settings, load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation import build_test_set, evaluate_pipeline
from ingestion import build_clean_dataframe, fetch_source_records
from observability import build_freshness_report, generate_phase1_report, run_data_quality_checks
from retrieval import LocalEmbeddingIndex

logger = logging.getLogger(__name__)


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Baseline end-to-end: Ingest -> Clean -> Index Chroma -> Testset -> Evaluate -> Quality Gate -> Report."""
    run_date = now_utc()

    # 1. Ingest
    records = fetch_source_records(settings)
    logger.info("Ingested %d raw records.", len(records))

    # 2. Clean + luu CSV/JSON
    df = build_clean_dataframe(records, run_date=run_date)
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    logger.info("Clean dataset: %d rows.", len(df))

    # 3. Index ChromaDB
    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=settings.paths.embeddings_json)

    # 4. Tao moi hoac dung lai evaluation set
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(df, settings.paths.eval_testset)

    # 5. Danh gia baseline (Hit Rate, Token F1, judge)
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    # 6. Quality Gate GX + freshness SLA
    quality = run_data_quality_checks(df, settings, report_name="baseline")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_rows": len(df),
        "dropped_rows": len(records) - len(df),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "run_date": run_date.date().isoformat(),
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)

    return {
        "source_summary": source_summary,
        "metrics": bundle.summary,
        "quality_success": quality["success"],
        "is_fresh": freshness["is_fresh"],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    result = run_phase1_pipeline(settings)
    metrics = result["metrics"]
    print(f"Clean rows: {result['source_summary']['clean_rows']} -> {settings.paths.clean_csv}")
    print(f"Retrieval Hit Rate: {metrics['retrieval_hit_rate']:.4f} | Mean Token F1: {metrics['mean_token_f1']:.4f}")
    print(f"Quality gate: {'PASS' if result['quality_success'] else 'FAIL'} | Freshness SLA: {'PASS' if result['is_fresh'] else 'FAIL'}")
    print(f"Report: {settings.paths.baseline_report}")
