# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `Sweet`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3B-Day10-Sweet-Data-Pipeline-Data-Observability`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Phạm Long Nhật | 2A202602844 | | Trưởng nhóm — Data Foundation & Observability (`crossref.py`, `cleaning.py`, `quality.py`) | `report/2A202602844_PhamLongNhat.md` |
| 2 | Trần Xuân Đức | 2A202602768 | | Evaluation, Corruption & Pipeline Integration (`testset.py`, `reporting.py`, `corruption.py`, `phase1.py`, `corruption_flow.py`) | `report/2A202602768_TranXuanDuc.md` |

---

## # Phân công theo Checkpoint

| Checkpoint | Owner chính | Hỗ trợ / Review | Deliverable |
|---|---|---|---|
| **CP0** — Môi trường, `.env`, Raw ingestion | Nhật | Đức (setup `.venv` + `.env` trên máy mình) | `src/ingestion/crossref.py`, `data/raw/crossref_response.json`, `data/raw/crossref_records.json` |
| **CP1** — Cleaning & GX 1.x + Freshness | Nhật | Đức (review clean schema trước khi dùng cho test set) | `src/ingestion/cleaning.py`, `src/observability/quality.py`, `data/clean/`, `data/quality/` |
| **CP2** — Test set & ChromaDB index | Đức | Nhật (review test set khớp clean schema) | `src/evaluation/testset.py`, `data/eval/test_set.json`, collection `papers-baseline` |
| **CP3** — Baseline end-to-end & báo cáo pha 1 | Đức | Nhật (xác minh quality/freshness trong báo cáo) | `src/pipelines/phase1.py`, `src/observability/reporting.py`, `baseline_metrics.json`, `data/reports/phase1_report.md` |
| **CP4** — Corruption suite (6 kịch bản) | Đức | Nhật (chạy quality gate trên dữ liệu bẩn) | `src/ingestion/corruption.py`, `corruption_log.json`, `corrupted_metrics.json` |
| **CP5** — Idempotent repair & báo cáo 3 trạng thái | Đức | Nhật (repair từ raw records) | `src/pipelines/corruption_flow.py`, `repaired_metrics.json`, `data/reports/corruption_report.md` |
| **CP6** — Demo, Q&A, nộp bài | Cả nhóm | — | `report/group_report.md`, báo cáo cá nhân, mỗi người tự nộp link LMS |

### Contract dùng chung (chốt trước khi làm song song)

| Contract | Owner | Nội dung |
|---|---|---|
| Raw schema | Nhật | `PaperRecord` trong `src/ingestion/crossref.py` (11 trường, `paper_id` = DOI viết thường) |
| Clean schema | Nhật | `CLEAN_COLUMNS` trong `src/ingestion/cleaning.py`: 11 trường raw + `age_days` (int), `authors_joined`, `categories_joined` (str, ngăn cách `, `), `summary_chars` (int), `text_for_embedding` (5 dòng `Title/Authors/Published/Categories/Summary`); `published`/`updated` dạng `YYYY-MM-DD` |
| Quality result | Nhật | `run_data_quality_checks(df, settings, report_name)` → dict `{success, row_count, failed_checks, checks, freshness{is_fresh, stale_rows, stale_ratio, ...}}`, ghi `data/quality/<report_name>_quality_report.json`; `build_freshness_report(df, settings, path)` → payload freshness |
| Evaluation set | Đức | Schema câu hỏi (`id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`) — dùng chung cho baseline / corrupted / repaired |
| Artifact paths | Cả nhóm | Chỉ dùng đường dẫn trong `src/core/config.py`, không hard-code |
| Repair source | Đức | Repair từ `data/raw/crossref_records.json` qua `load_raw_records` + `build_clean_dataframe` |

---

## # Cá nhân

### ## PhamLongNhat-2A202602844
- **Vai trò:** Trưởng nhóm — Data Foundation & Observability owner.
- **Phần việc sở hữu:**
  - `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records` (retry 429/5xx + fallback snapshot offline), `load_raw_records`.
  - `src/ingestion/cleaning.py`: `build_clean_dataframe` (bỏ thẻ JATS, chuẩn hóa text, `age_days`, dedupe theo `paper_id`, `text_for_embedding`).
  - `src/observability/quality.py`: Quality Gate Great Expectations 1.x (4 expectations bắt buộc) + Freshness SLA (`age_days > 180`, cảnh báo khi > 25% bài cũ).
  - Quản lý repo nhánh `main`, `report/group_report.md`.
- **Trạng thái:**
  - ✅ CP0 `crossref.py` — `Tín hiệu hoàn thành: Đã tải 24 bài báo`; fallback 429/offline đã kiểm thử (commit `1135634`).
  - ✅ CP1 `cleaning.py` — `Clean thành công 24 dòng`; artifact `data/clean/papers_clean.{csv,json}` (commit `5723818`).
  - ✅ CP1 `quality.py` — `Quality check status = True`, 6/6 expectation pass, freshness 1/24 bài cũ → `is_fresh = True`; artifact `data/quality/test_quality_report.json` (commit `4ac6bdf`).
  - ⏳ `report/group_report.md` — chờ số liệu phase1 và corruption flow.
- **Báo cáo chi tiết:** `report/2A202602844_PhamLongNhat.md`
- **Điều học được / Đóng góp chính:** _(tự điền)_

### ## TranXuanDuc-2A202602768
- **Vai trò:** Evaluation, Corruption & Pipeline Integration owner.
- **Phần việc sở hữu:**
  - `src/evaluation/testset.py`: bộ 10 câu hỏi thuộc 4 dạng `summary` / `authors` / `date` / `categories`.
  - `src/observability/reporting.py`: sinh `phase1_report.md` và `corruption_report.md`.
  - `src/ingestion/corruption.py`: 6 kịch bản làm bẩn dữ liệu.
  - `src/pipelines/phase1.py`: nối luồng baseline end-to-end (clean → index ChromaDB → eval → quality → report).
  - `src/pipelines/corruption_flow.py`: corrupted → đo suy giảm → idempotent repair → so sánh 3 trạng thái.
- **Trạng thái:**
  - ✅ CP2 `testset.py` — `Tín hiệu hoàn thành: Sinh được 10 câu hỏi test`; phân bổ 3 `summary` / 3 `authors` / 2 `date` / 2 `categories`, mỗi câu một paper khác nhau, câu hỏi khớp intent của `retrieval/qa.py`; artifact `data/eval/test_set.json`.
  - ✅ CP3 `phase1.py` + `reporting.py` — `python script/run_phase1.py` exit 0: 24/24 dòng sạch, collection `papers-baseline`, Hit Rate = 1.0, Token F1 = 1.0, GX 6/6 pass, freshness 1/24 → `is_fresh = True`; artifact `data/results/baseline_metrics.json`, `data/reports/phase1_report.md`.
  - ✅ CP4 `corruption.py` — `Tín hiệu hoàn thành: Corrupted 21 dòng` (seed 42, tái lập được): drop latest 5, blank summary 3, inject noise 3, truncate title 3, stale date 4, duplicate 2; artifact `data/results/corruption_log.json`.
  - ✅ CP5 `corruption_flow.py` — `python script/run_corruption_flow.py` exit 0: Hit Rate 1.0 → 0.5 → 1.0, Token F1 1.0 → 0.73 → 1.0 (phục hồi 100%); GX corrupted FAIL (`paper_id` trùng, summary rỗng), repaired PASS; artifact `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md`.
  - ⚠️ Lưu ý LLM judge: chấm bằng Ollama `qwen2.5:3b` (local; Gemini free tier chỉ 20 request/ngày, không đủ 30 lượt judge), 30/30 câu được LLM chấm thật, không fallback. Judge Accuracy 0.7 → 0.4 → 0.6, Mean Judge Score 3.6 → 2.9 → 3.7. Model 3B chấm thiếu ổn định (vd. câu `date` trả lời đúng tuyệt đối vẫn bị 1 điểm vì model cho rằng năm 2026 "không hợp lệ") → dùng Hit Rate và Token F1 làm chỉ số chính, judge chỉ tham khảo.
  - ⚠️ Freshness SLA corrupted vẫn PASS (stale ratio 0.238, sát ngưỡng 0.25) — ghi nhận trong báo cáo nhóm.
  - ✅ Báo cáo cá nhân `report/2A202602768_TranXuanDuc.md` (chờ tự đánh dấu mục cam kết).
  - ⏳ Commit code + artifact CP2–CP5.
- **Báo cáo chi tiết:** `report/2A202602768_TranXuanDuc.md`
- **Điều học được / Đóng góp chính:**
  - Nối toàn bộ luồng Baseline → Corrupted → Repaired và báo cáo đối chiếu 3 trạng thái (bảng metric, Hit Rate theo dạng câu hỏi, quality gate, freshness, tỷ lệ phục hồi).
  - Silent failure là có thật: pipeline RAG chạy trên dữ liệu bẩn không báo lỗi nhưng Hit Rate giảm 50% — chỉ lớp observability (GX Quality Gate) phát hiện được sự cố.
  - Repair idempotent từ raw snapshot bất biến + dùng lại đúng hàm clean giúp khôi phục hoàn toàn, chạy lại nhiều lần vẫn cho cùng kết quả.
  - Bộ test set phải khớp với logic nhận diện câu hỏi của hệ thống QA; nếu lệch wording, metric giảm sai lệch dù dữ liệu sạch.
