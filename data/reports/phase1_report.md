# Phase 1 Report - Baseline Pipeline

_Generated at: 2026-09-26T04:32:41.260586+00:00_

## 1. Source Data

| Item | Value |
|---|---|
| Source api | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-03-30,has-abstract:true |
| Raw records | 24 |
| Clean rows | 24 |
| Dropped rows | 0 |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Collection | papers-baseline |
| Run date | 2026-09-26 |

## 2. Baseline Evaluation

| Metric | Value |
|---|---|
| Samples | 10 |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| Judge Accuracy | 0.7000 |
| Mean Judge Score (1-5) | 3.6000 |

- Ragas: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## 3. Data Quality Gate (Great Expectations)

- Overall gate: **PASS** (row count: 24)
- Failed checks: none

| Expectation | Column | Result | Observed | Unexpected |
|---|---|---|---|---|
| expect_table_row_count_to_be_between | - | PASS | 24 | - |
| expect_column_values_to_not_be_null | paper_id | PASS | - | 0 |
| expect_column_values_to_be_unique | paper_id | PASS | - | 0 |
| expect_column_values_to_not_be_null | title | PASS | - | 0 |
| expect_column_values_to_not_be_null | text_for_embedding | PASS | - | 0 |
| expect_column_value_lengths_to_be_between | summary | PASS | - | 0 |

## 4. Freshness SLA

| Item | Value |
|---|---|
| Latest published | 2026-07-22 |
| Oldest published | 2026-03-28 |
| Threshold (days) | 180 |
| Stale rows / total | 1 / 24 |
| Stale ratio (max allowed) | 0.0417 (0.2500) |
| SLA status | PASS |
