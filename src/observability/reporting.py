from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(_fmt(cell) for cell in row) + " |" for row in rows)
    return lines


def _metrics_rows(metrics: dict[str, Any]) -> list[list[Any]]:
    return [
        ["Samples", metrics.get("samples")],
        ["Retrieval Hit Rate", metrics.get("retrieval_hit_rate")],
        ["Mean Token F1", metrics.get("mean_token_f1")],
        ["Judge Accuracy", metrics.get("judge_accuracy")],
        ["Mean Judge Score (1-5)", metrics.get("mean_judge_score")],
    ]


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    lines = [
        f"- Overall gate: **{_fmt(quality.get('success'))}** (row count: {quality.get('row_count')})",
        f"- Failed checks: {', '.join(quality.get('failed_checks') or []) or 'none'}",
        "",
    ]
    rows = [
        [
            check.get("expectation"),
            check.get("column"),
            check.get("success"),
            check.get("observed_value"),
            check.get("unexpected_count"),
        ]
        for check in quality.get("checks", [])
    ]
    return lines + _table(["Expectation", "Column", "Result", "Observed", "Unexpected"], rows)


def _freshness_rows(freshness: dict[str, Any]) -> list[list[Any]]:
    return [
        ["Latest published", freshness.get("latest_published")],
        ["Oldest published", freshness.get("oldest_published")],
        ["Threshold (days)", freshness.get("threshold_days")],
        ["Stale rows / total", f"{freshness.get('stale_rows')} / {freshness.get('total_rows')}"],
        ["Stale ratio (max allowed)", f"{_fmt(freshness.get('stale_ratio'))} ({_fmt(freshness.get('max_stale_ratio'))})"],
        ["SLA status", freshness.get("is_fresh")],
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase: nguon du lieu, metrics, quality gate va freshness SLA."""
    source_rows = [[key.replace("_", " ").capitalize(), value] for key, value in source_summary.items()]
    ragas = metrics.get("ragas") or {}
    ragas_note = ragas.get("skipped") or ragas.get("error") or ", ".join(f"{k}={_fmt(v)}" for k, v in ragas.items())

    lines = [
        "# Phase 1 Report - Baseline Pipeline",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Source Data",
        "",
        *_table(["Item", "Value"], source_rows),
        "",
        "## 2. Baseline Evaluation",
        "",
        *_table(["Metric", "Value"], _metrics_rows(metrics)),
        "",
        f"- Ragas: {ragas_note or '-'}",
        "",
        "## 3. Data Quality Gate (Great Expectations)",
        "",
        *_quality_lines(quality),
        "",
        "## 4. Freshness SLA",
        "",
        *_table(["Item", "Value"], _freshness_rows(freshness)),
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))


STATES = ("Baseline", "Corrupted", "Repaired")
COMPARED_METRICS = (
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "Judge Accuracy"),
    ("mean_judge_score", "Mean Judge Score (1-5)"),
)


def _recovery(baseline: float, corrupted: float, repaired: float) -> str:
    drop = baseline - corrupted
    if abs(drop) < 1e-9:
        return "n/a (no drop)"
    return f"{(repaired - corrupted) / drop:.0%}"


def comparison_rows(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> list[list[Any]]:
    """Moi metric mot dong: gia tri 3 trang thai, muc sut giam va ty le phuc hoi."""
    rows = []
    for key, label in COMPARED_METRICS:
        base, bad, fixed = (float(m.get(key) or 0.0) for m in (baseline_metrics, corrupted_metrics, repaired_metrics))
        rows.append([label, base, bad, fixed, f"{bad - base:+.4f}", _recovery(base, bad, fixed)])
    return rows


COMPARISON_HEADERS = ["Metric", *STATES, "Delta (Corrupted - Baseline)", "Recovery"]


def format_comparison_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> str:
    rows = [COMPARISON_HEADERS] + [
        [_fmt(cell) for cell in row] for row in comparison_rows(baseline_metrics, corrupted_metrics, repaired_metrics)
    ]
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(COMPARISON_HEADERS))]
    lines = [" | ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)) for row in rows]
    lines.insert(1, "-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def _hit_rate_by_type(answers: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, list[float]] = {}
    for answer in answers:
        totals.setdefault(answer["question_type"], []).append(1.0 if answer["retrieval_hit"] else 0.0)
    return {name: sum(values) / len(values) for name, values in totals.items()}


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    answers_by_state: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    """Viet markdown report so sanh Baseline / Corrupted / Repaired: metrics, quality gate, freshness, phan tich."""
    qualities = (baseline_quality or {}, corrupted_quality, repaired_quality)
    baseline_freshness = baseline_freshness or (baseline_quality or {}).get("freshness") or {}
    freshnesses = (baseline_freshness, corrupted_freshness, repaired_freshness)

    lines = [
        "# Corruption Report - Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Injected Corruptions",
        "",
    ]
    if corruption_log:
        lines += [
            f"- Rows: {corruption_log.get('input_rows')} clean -> {corruption_log.get('output_rows')} corrupted "
            f"(seed={corruption_log.get('seed')})",
            "",
            *_table(["Corruption", "Affected rows"], [[k, v] for k, v in corruption_log.get("corruption_counts", {}).items()]),
        ]
    else:
        lines.append("- Corruption log not provided.")

    lines += [
        "",
        "## 2. RAG Performance",
        "",
        *_table(COMPARISON_HEADERS, comparison_rows(baseline_metrics, corrupted_metrics, repaired_metrics)),
        "",
        "_Recovery = (Repaired - Corrupted) / (Baseline - Corrupted)._",
        "",
    ]
    if answers_by_state:
        by_type = {state: _hit_rate_by_type(answers_by_state.get(state, [])) for state in STATES}
        types = sorted({name for values in by_type.values() for name in values})
        lines += [
            "### Retrieval Hit Rate by question type",
            "",
            *_table(["Question type", *STATES], [[t, *(by_type[s].get(t) for s in STATES)] for t in types]),
            "",
        ]

    lines += [
        "## 3. Data Quality Gate (Great Expectations)",
        "",
        *_table(
            ["Item", *STATES],
            [
                ["Gate", *(q.get("success") for q in qualities)],
                ["Row count", *(q.get("row_count") for q in qualities)],
                ["Failed checks", *(", ".join(q.get("failed_checks") or []) or "none" if q else None for q in qualities)],
            ],
        ),
        "",
        "## 4. Freshness SLA",
        "",
        *_table(
            ["Item", *STATES],
            [
                ["Stale rows / total", *(f"{f.get('stale_rows')} / {f.get('total_rows')}" if f else None for f in freshnesses)],
                ["Stale ratio", *(f.get("stale_ratio") for f in freshnesses)],
                ["Latest published", *(f.get("latest_published") for f in freshnesses)],
                ["SLA status", *(f.get("is_fresh") for f in freshnesses)],
            ],
        ),
        "",
        "## 5. Analysis",
        "",
    ]

    hit_drop = float(baseline_metrics.get("retrieval_hit_rate", 0)) - float(corrupted_metrics.get("retrieval_hit_rate", 0))
    f1_drop = float(baseline_metrics.get("mean_token_f1", 0)) - float(corrupted_metrics.get("mean_token_f1", 0))
    lines += [
        f"- **Silent failure:** the RAG pipeline ran on corrupted data without raising any error, yet Hit Rate dropped "
        f"by {hit_drop:.2f} and Token F1 by {f1_drop:.2f}. Only the observability layer surfaced the incident: "
        f"quality gate = {_fmt(corrupted_quality.get('success'))} "
        f"(failed: {', '.join(corrupted_quality.get('failed_checks') or []) or 'none'}), "
        f"freshness SLA = {_fmt(corrupted_freshness.get('is_fresh'))}.",
        "- **Repair:** the dataset was rebuilt from the immutable raw snapshot with the same cleaning code, so the "
        "repair is idempotent - running it again yields the same rows.",
        f"- **Recovery:** Hit Rate {_recovery(float(baseline_metrics.get('retrieval_hit_rate', 0)), float(corrupted_metrics.get('retrieval_hit_rate', 0)), float(repaired_metrics.get('retrieval_hit_rate', 0)))}, "
        f"Token F1 {_recovery(float(baseline_metrics.get('mean_token_f1', 0)), float(corrupted_metrics.get('mean_token_f1', 0)), float(repaired_metrics.get('mean_token_f1', 0)))}; "
        f"repaired quality gate = {_fmt(repaired_quality.get('success'))}, freshness SLA = {_fmt(repaired_freshness.get('is_fresh'))}.",
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))
