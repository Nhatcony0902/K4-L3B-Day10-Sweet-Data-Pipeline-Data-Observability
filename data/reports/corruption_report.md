# Corruption Report - Baseline vs Corrupted vs Repaired

_Generated at: 2026-09-26T04:38:57.346240+00:00_

## 1. Injected Corruptions

- Rows: 24 clean -> 21 corrupted (seed=42)

| Corruption | Affected rows |
|---|---|
| drop_latest_records | 5 |
| blank_summary | 3 |
| inject_noise | 3 |
| truncate_title | 3 |
| stale_date | 4 |
| duplicate_rows | 2 |

## 2. RAG Performance

| Metric | Baseline | Corrupted | Repaired | Delta (Corrupted - Baseline) | Recovery |
|---|---|---|---|---|---|
| Retrieval Hit Rate | 1.0000 | 0.5000 | 1.0000 | -0.5000 | 100% |
| Mean Token F1 | 1.0000 | 0.7269 | 1.0000 | -0.2731 | 100% |
| Judge Accuracy | 0.7000 | 0.4000 | 0.6000 | -0.3000 | 67% |
| Mean Judge Score (1-5) | 3.6000 | 2.9000 | 3.7000 | -0.7000 | 114% |

_Recovery = (Repaired - Corrupted) / (Baseline - Corrupted)._

### Retrieval Hit Rate by question type

| Question type | Baseline | Corrupted | Repaired |
|---|---|---|---|
| authors | 1.0000 | 0.6667 | 1.0000 |
| categories | 1.0000 | 0.5000 | 1.0000 |
| date | 1.0000 | 0.5000 | 1.0000 |
| summary | 1.0000 | 0.3333 | 1.0000 |

## 3. Data Quality Gate (Great Expectations)

| Item | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Gate | PASS | FAIL | PASS |
| Row count | 24 | 21 | 24 |
| Failed checks | none | expect_column_values_to_be_unique, expect_column_value_lengths_to_be_between | none |

## 4. Freshness SLA

| Item | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Stale rows / total | 1 / 24 | 5 / 21 | 1 / 24 |
| Stale ratio | 0.0417 | 0.2381 | 0.0417 |
| Latest published | 2026-07-22 | 2026-06-11 | 2026-07-22 |
| SLA status | PASS | PASS | PASS |

## 5. Analysis

- **Silent failure:** the RAG pipeline ran on corrupted data without raising any error, yet Hit Rate dropped by 0.50 and Token F1 by 0.27. Only the observability layer surfaced the incident: quality gate = FAIL (failed: expect_column_values_to_be_unique, expect_column_value_lengths_to_be_between), freshness SLA = PASS.
- **Repair:** the dataset was rebuilt from the immutable raw snapshot with the same cleaning code, so the repair is idempotent - running it again yields the same rows.
- **Recovery:** Hit Rate 100%, Token F1 100%; repaired quality gate = PASS, freshness SLA = PASS.
