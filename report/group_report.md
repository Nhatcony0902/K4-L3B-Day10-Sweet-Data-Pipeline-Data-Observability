# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4 |
| Tên nhóm         | Sweet |
| Repository         | https://github.com/Nhatcony0902/K4-L3B-Day10-Sweet-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Phạm Long Nhật (trưởng nhóm) | 2A202602844 | Data Foundation & Observability | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/observability/quality.py`; `data/raw/`, `data/clean/papers_clean.*` |
| 2 | Trần Xuân Đức | 2A202602768 | Evaluation, Corruption & Pipeline Integration | `src/evaluation/testset.py`, `src/observability/reporting.py`, `src/ingestion/corruption.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`; `data/eval/`, `data/results/`, `data/reports/` |

> Nhóm có 2 thành viên (ít hơn khuyến nghị 3–5 người trong `report/README.md`); mỗi người nhận nhiều khối, phạm vi ghi rõ trong `docs/TEAM.md` và báo cáo cá nhân.

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm hoàn thành toàn bộ pipeline bắt buộc: ingestion Crossref có retry và fallback snapshot, cleaning, embedding MiniLM + ChromaDB, bộ đánh giá 10 câu, quality gate Great Expectations 1.x cùng freshness SLA, 6 kịch bản corruption, repair và báo cáo đối chiếu ba trạng thái. Cả `run_phase1.py` và `run_corruption_flow.py` đều chạy exit 0.

Baseline tạo ra raw records (24 bài), clean dataset 24 dòng, collection `papers-baseline`, `test_set.json`, `baseline_metrics.json` (Hit Rate 1.0, Token F1 1.0), các quality/freshness report và `phase1_report.md`.

Corruption ảnh hưởng rõ nhất là **drop 20% bài mới nhất**: toàn bộ 5/10 câu retrieval miss đều hỏi về các bài bị xóa, Hit Rate giảm 1.0 → 0.5, trong khi pipeline RAG vẫn trả lời đủ 10 câu mà không báo lỗi. Quality gate chuyển sang FAIL nhờ duplicate `paper_id` và summary rỗng, nhưng không có tín hiệu nào bắt được chính lỗi mất bài; freshness vẫn PASS (0.238 < 0.25).

Repair dựng lại dataset từ raw snapshot bằng chính hàm cleaning, cho kết quả giống hệt baseline, nên Hit Rate và Token F1 phục hồi 100%, gate PASS.

Giới hạn lớn nhất: LLM judge `qwen2.5:3b` chấm không ổn định (judge accuracy baseline 0.7 nhưng repaired 0.6 dù câu trả lời giống hệt), và quality gate chỉ bắt được 2/6 loại corruption.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref snapshot (data/raw/crossref_response.json; API thật khi REFRESH_SOURCE=1)
    -> parse -> data/raw/crossref_records.json                     [crossref.py]
    -> build_clean_dataframe -> data/clean/papers_clean.{csv,json} [cleaning.py]
    -> MiniLM embedding + ChromaDB papers-baseline                  [retrieval/index.py]
    -> build_test_set -> data/eval/test_set.json                    [testset.py]
    -> evaluate baseline -> data/results/baseline_*.json            [evaluation/metrics.py]
    -> GX quality gate + freshness -> data/quality/                 [quality.py]
    -> phase1_report.md                                             [reporting.py]
    -> corrupt_clean_dataframe -> corruption_log.json               [corruption.py]
    -> re-index papers-corrupted + re-evaluate + quality gate
    -> repair_from_raw_snapshot (raw records -> build_clean_dataframe)
    -> re-index papers-repaired + re-evaluate + quality gate
    -> corruption_report.md                                         [corruption_flow.py, reporting.py]
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref `/works` JSON (snapshot hoặc API) | Retry 429/5xx (3 lần, backoff, `Retry-After`), fallback snapshot, parse + bỏ thẻ JATS | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nhật |
| Cleaning          | `list[PaperRecord]`, `run_date` | Chuẩn hóa text/list, loại dòng thiếu trường bắt buộc, `age_days`, dedupe `paper_id`, `text_for_embedding` | `data/clean/papers_clean.{csv,json}` | Nhật |
| Embedding/index   | Clean DataFrame | `all-MiniLM-L6-v2`, ChromaDB persistent, 1 collection mỗi trạng thái | `data/chroma/`, `data/embeddings/*.json` | Có sẵn trong starter; Đức tích hợp |
| Evaluation        | Clean DataFrame, index | Test set 10 câu tất định; Hit Rate, Token F1, LLM judge | `data/eval/test_set.json`, `data/results/*_metrics.json`, `*_answers.json` | Đức |
| Observability     | Clean/corrupted/repaired DataFrame | GX 1.x ephemeral: row count, not-null ×3, unique, summary length; freshness SLA | `data/quality/*_quality_report.json`, `freshness_report.json` | Nhật |
| Corruption/repair | Clean DataFrame; raw records | 6 lỗi có seed 42; repair = rebuild từ raw bằng `build_clean_dataframe` | `data/results/corruption_log.json`, `data/clean/papers_clean_{corrupted,repaired}.*` | Đức |
| Orchestration     | `Settings` | Phase 1 → corruption flow; test set dùng lại | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Đức |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `ollama` (local) |
| `LLM_MODEL`                | `qwen2.5:3b` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 (`max_results = 24`) |
| Retrieval`top_k`           | 4 |
| Freshness threshold          | 180 ngày; cảnh báo khi > 25% bài cũ |
| Random seed, nếu có        | 42 (corruption) |
| `REFRESH_SOURCE`             | để trống → dùng snapshot trong repo |

### Lệnh cài đặt

```bash
uv venv --python 3.11
uv sync --extra dev
```

### Lệnh chạy

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (exit 0) | 2026-09-26 11:32 (UTC+7) | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công (exit 0) | 2026-09-26 11:38 (UTC+7) | `data/reports/corruption_report.md`, `data/results/{corrupted,repaired}_metrics.json` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API `https://api.crossref.org/works`; lượt chạy nộp bài dùng snapshot offline `data/raw/crossref_response.json` có sẵn trong repo |
| Query/filter                | `query = "agentic retrieval augmented generation large language model"`, `filter = from-pub-date:<run_date − 180 ngày>,has-abstract:true` (lượt chạy: `from-pub-date:2026-03-30`), `rows = 24` |
| Thời điểm lấy dữ liệu | Snapshot của starter repo; không gọi API trong lượt chạy nộp bài |
| Số record nhận được    | 24 item → 24 `PaperRecord` hợp lệ |
| Cơ chế retry/backoff      | Tối đa 3 lần cho 429/500/502/503/504 và lỗi mạng; chờ `Retry-After` hoặc 2^attempt giây; hết lượt → fallback snapshot |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | str | Có | DOI viết thường — document ID | Thiếu → loại record; trùng → giữ bản `updated` mới nhất |
| `title` | str | Có | Tiêu đề (phần tử đầu không rỗng của `title[]`) | Thiếu → loại record |
| `summary` | str | Có | Abstract đã bỏ thẻ JATS/HTML và tiêu đề `Abstract` | Thiếu → loại record |
| `authors` | list[str] | Không | `given family` hoặc `name` (tác giả tổ chức) | Thiếu → `[]` |
| `categories` | list[str] | Không | Crossref `subject` | Thiếu → `[]` |
| `primary_category` | str | Không | Category đầu tiên | Thiếu → `""` |
| `published` | str `YYYY-MM-DD` | Có | Ưu tiên `published → published-print → published-online → issued → created`; thiếu tháng/ngày → 01 | Không parse được → loại record |
| `updated` | str `YYYY-MM-DD` | Không | `updated` hoặc `created` | Thiếu → bằng `published` |
| `abs_url`, `pdf_url` | str | Không | `URL`; link `application/pdf` nếu có | Thiếu → `https://doi.org/<DOI>` |
| `age_days` | int | Có (clean) | `run_date − published` | Tính lại mỗi lần chạy |
| `authors_joined`, `categories_joined` | str | Có (clean) | Nối bằng `, ` — dùng làm metadata Chroma | `""` nếu list rỗng |
| `summary_chars` | int | Có (clean) | Độ dài summary | — |
| `text_for_embedding` | str | Có (clean) | 5 dòng `Title / Authors / Published / Categories / Summary` | — |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ thẻ JATS/HTML (`<jats:p>`, `<title>Abstract</title>`) và gộp khoảng trắng | Validity / Consistency | 24 | 24/24 abstract trong raw có thẻ; `papers_clean.json` không còn thẻ |
| Loại record thiếu `paper_id`/`title`/`summary` hoặc ngày không hợp lệ | Completeness / Validity | 0 | `phase1_report.md`: Raw 24 → Clean 24, Dropped 0 |
| Dedupe `paper_id` (giữ `updated` mới nhất) | Uniqueness | 0 | GX `expect_column_values_to_be_unique` PASS ở baseline |
| Chuẩn hóa list authors/categories (bỏ rỗng, bỏ trùng) | Consistency | 0 | So sánh records ↔ clean |

Cách tạo các trường dẫn xuất: `paper_id` là DOI viết thường nên ổn định qua mọi lần chạy và dùng làm `ground_truth_doc_ids`. `age_days` được tính tại thời điểm chạy, nên freshness phản ánh độ mới thật của corpus. `text_for_embedding` ghép 5 phần, để embedding nắm được cả metadata (tác giả, ngày, lĩnh vực) chứ không chỉ nội dung tóm tắt.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 |
| Các`question_type`                    | `summary` 3, `authors` 3, `date` 2, `categories` 2 |
| Ground-truth document ID                 | `paper_id` (DOI) của paper được hỏi; mỗi câu một paper khác nhau |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB persistent `data/chroma/`; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval`top_k`                       | 4 |
| LLM provider/model                       | Ollama `qwen2.5:3b` (judge) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 bắt đầu bằng `9536fd0d51c4`); đã kiểm tra id + câu hỏi trùng 10/10 ở cả 3 `*_answers.json` |

Test set chỉ được sinh một lần từ baseline, và chỉ sinh lại khi đặt `REFRESH_TEST_SET=1`. Nếu sinh lại từ bản corrupted, các câu hỏi về 5 bài bị xóa sẽ biến mất và Hit Rate trông vẫn tốt, che mất đúng sự cố cần đo. Giữ nguyên test set đảm bảo mọi chênh lệch metric chỉ đến từ dữ liệu.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | 24 item / 24 records |
| Cleaned dataset          | `data/clean/`                        | Có | `papers_clean.{csv,json}` 24 dòng; kèm bản corrupted/repaired |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/`   | Có | 3 manifest + 3 collection |
| Evaluation set           | `data/eval/`                         | Có | `test_set.json` 10 câu |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json` |
| Quality/freshness        | `data/quality/`                      | Có | `baseline/corrupted/repaired_quality_report.json`, `freshness_report.json` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | — |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | 1.00 | 10/10 câu lấy được đúng paper trong top-4 |
| `mean_token_f1`      | 1.00 | `qa.py` tra paper theo title rồi trả thẳng trường metadata, nên baseline là mức trần, không đo năng lực sinh câu trả lời của LLM |
| `judge_accuracy`     | 0.70 | 3 câu bị chấm sai, trong đó 2 câu `date` trả lời khớp tuyệt đối nhưng judge cho rằng năm 2026 "không hợp lệ" |
| `mean_judge_score`   | 3.6 | Như trên |
| Ragas, nếu có        | N/A | Không bật (`RUN_RAGAS=1`) để giữ thời gian chạy ngắn |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `expect_table_row_count_to_be_between` | Volume | 5 – 5000 dòng | PASS (24) | `data/quality/baseline_quality_report.json` |
| `expect_column_values_to_not_be_null` × 3 | Completeness | `paper_id`, `title`, `text_for_embedding` không null | PASS (0 dòng lỗi mỗi cột) | như trên |
| `expect_column_values_to_be_unique` | Uniqueness | `paper_id` duy nhất | PASS (0) | như trên |
| `expect_column_value_lengths_to_be_between` | Completeness / Validity | `summary` ≥ 30 ký tự | PASS (0; min thực tế 193) | như trên |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Clean dataset (`age_days`) — `data/quality/freshness_report.json` |
| Timestamp mới nhất       | `published` 2026-07-22 (cũ nhất 2026-03-28) |
| Ngưỡng freshness         | `age_days > 180` là stale; `is_fresh = False` khi stale ratio > 0.25 |
| Trạng thái baseline      | Fresh |
| Lý do                     | 1/24 bài quá 180 ngày → stale ratio 0.042 ≤ 0.25 |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest_records` | Bỏ `ceil(20%)` bài có `published` mới nhất | 5 | Row count giảm, freshness xấu đi | Không check nào FAIL (21 trong 5–5000); `latest_published` 2026-07-22 → 2026-06-11; gây toàn bộ 5 retrieval miss | Rebuild từ raw records |
| `blank_summary` | `summary = ""` | 3 | Summary length FAIL | ✅ `expect_column_value_lengths_to_be_between` FAIL, 3 dòng; `not_null` vẫn PASS vì `""` ≠ null | Rebuild từ raw records |
| `inject_noise` | Chèn 3 token rác (`NULL`, `0xDEADBEEF`, …) vào đầu/giữa/cuối summary | 3 | Không có check tương ứng | Không bị phát hiện; paper không nằm trong test set | Rebuild từ raw records |
| `truncate_title` | Cắt title còn 7 ký tự | 3 | Không có check tương ứng | Không bị phát hiện; `eval_009` vẫn hit nhờ summary/authors | Rebuild từ raw records |
| `stale_date` | Lùi `published`/`updated` 365 ngày, cộng `age_days` | 4 | Freshness FAIL | Stale ratio 0.042 → 0.238, vẫn dưới 0.25 → PASS | Rebuild từ raw records |
| `duplicate_rows` | Nhân đôi dòng | 2 | Unique FAIL | ✅ `expect_column_values_to_be_unique` FAIL, 4 dòng | Rebuild từ raw records |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: log đủ 6 loại lỗi, gồm seed (42), `input_rows`/`output_rows` (24 → 21), `corruption_counts`, và 20 entry ghi `paper_id`, trường bị sửa, giá trị `before`/`after` cho từng dòng. Các nhóm dòng không giao nhau nên tác động của từng loại lỗi được tách riêng.

Repair không đọc gì từ bản corrupted và không dùng log để "hoàn tác". `repair_from_raw_snapshot` đọc `data/raw/crossref_records.json`, tức mốc lineage được lưu ngay lúc ingestion, rồi chạy lại đúng hàm `build_clean_dataframe` đã qua quality gate ở baseline. Nhờ vậy repair lấy lại được cả 5 bài bị xóa, điều mà cách sửa trên bản bẩn không làm được. Chạy lại bao nhiêu lần cũng cho cùng kết quả (idempotent). Đã kiểm tra `papers_clean_repaired.json` giống hệt `papers_clean.json` ở mọi cột trừ `age_days` (cột này phụ thuộc thời điểm chạy).

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | 1.00 | 0.50 | 1.00 | −0.50 | 100% | Cả 5 miss (`eval_001`–`005`) hỏi về 5 bài bị drop |
| `mean_token_f1`        | 1.00 | 0.727 | 1.00 | −0.273 | 100% | Giảm ít hơn Hit Rate vì có câu đúng tình cờ từ paper sai |
| `judge_accuracy`       | 0.70 | 0.40 | 0.60 | −0.30 | 67% | Không phục hồi hết dù answers repaired trùng baseline 10/10 → nhiễu của judge |
| `mean_judge_score`     | 3.6 | 2.9 | 3.7 | −0.7 | 114% | Như trên |
| Quality checks pass/fail | PASS 6/6 | FAIL 4/6 | PASS 6/6 | −2 check | 100% | Fail unique (4 dòng) và summary length (3 dòng) |
| Freshness status         | Fresh (0.042) | Fresh (0.238) | Fresh (0.042) | +0.196 stale ratio | 100% | Không đổi trạng thái vì sát ngưỡng 0.25 |

_Mức phục hồi = (Repaired − Corrupted) / (Baseline − Corrupted)._

Kết luận có quan hệ nhân quả:

1. **Drop 5 bài mới nhất** → không có quality signal nào FAIL (row count 21 vẫn hợp lệ, freshness 0.238 < 0.25) → Hit Rate 1.0 → 0.5 và Token F1 1.0 → 0.727. Agent vẫn trả lời đủ 10/10 câu, nhưng lấy từ paper sai. Đây là silent failure không bị quality gate chặn.
2. **Duplicate + blank summary** → GX gate PASS → FAIL (unique 4 dòng, summary length 3 dòng) → gate phát hiện sự cố trước khi dữ liệu vào index, dù riêng hai lỗi này không làm miss retrieval ở 10 câu hỏi.
3. **Repair từ raw snapshot** → GX PASS 6/6, stale ratio về 0.042, dataset giống hệt baseline → Hit Rate và Token F1 phục hồi 100%, answers và retrieved doc IDs trùng baseline 10/10. Judge metrics không về đúng baseline (0.6 so với 0.7): đây là nhiễu của model judge, không phải do dữ liệu.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** sau khi chạy lệnh kiểm tra CP0 lần đầu, `data/raw/crossref_response.json` và `crossref_records.json` bị thay bằng dữ liệu Crossref thật. Cả 24/24 bài có `categories: []`, có bài tiếng Nga, và summary bắt đầu bằng chữ "Abstract". Test set bắt buộc có dạng câu hỏi `categories`, nên các câu này sẽ không có ground truth.
- **Nguyên nhân:** bản đầu của `fetch_source_records` luôn gọi API và ghi đè snapshot. Crossref hiện không trả trường `subject`. Abstract thật chứa `<title>Abstract</title>`, và regex bỏ thẻ chỉ xóa thẻ nhưng giữ lại chữ "Abstract". Đây là lỗi hợp đồng giữa ingestion (Nhật) và evaluation set (Đức): dữ liệu đầu vào thay đổi theo lần chạy.
- **Cách xử lý:** khôi phục snapshot bằng `git checkout -- data/raw/`. `fetch_source_records` mặc định đọc snapshot, chỉ gọi API khi đặt `REFRESH_SOURCE=1` (có ghi trong `.env.example`). `clean_markup_text` bỏ cả khối `<(jats:)?title>…</(jats:)?title>`.
- **Cách xác minh:** chạy lệnh CP0 in ra 24 bài và `git diff -- data/raw/` rỗng. Khi đặt `REFRESH_SOURCE=1`, gọi API thật ra 24 bài; mock lỗi 429 và mock mất mạng đều fallback về 24 bài. Test set sinh ra đủ 2 câu `categories` có ground truth.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Quality gate chỉ bắt 2/6 loại corruption; bỏ sót mất bài mới, noise, title bị cắt | Sự cố gây thiệt hại lớn nhất (Hit Rate −50%) vẫn đi qua gate | Thêm check volume so với lần chạy trước (row count giảm > 10%), `latest_published` không được lùi, độ dài title ≥ 15 ký tự. Kỳ vọng: chạy lại corruption flow thì các check này FAIL ở corrupted và PASS ở repaired |
| Freshness chỉ dùng một ngưỡng tỷ lệ | Stale ratio 0.238 sát ngưỡng 0.25 nhưng không cảnh báo | Thêm tín hiệu tuyệt đối (tuổi của bài mới nhất) và mức cảnh báo sớm (ví dụ 0.2); đo lại trên `corrupted_quality_report.json` |
| LLM judge `qwen2.5:3b` không ổn định | Judge accuracy baseline 0.7 nhưng repaired 0.6 dù câu trả lời giống hệt | Dùng judge mạnh hơn hoặc chấm mỗi câu nhiều lần lấy trung vị. Tiêu chí: độ lệch judge giữa baseline và repaired về 0 |
| Judge lỗi thì âm thầm fallback sang heuristic (`evaluation/metrics.py`) | Metric có thể trông bình thường dù không có LLM chấm | Đếm số lần fallback và ghi vào `*_metrics.json`, fail khi lớn hơn 0 |
| Snapshot có khoảng 12 summary mất chữ cái đầu ("An extended empirical study on **onnecting**…") | Nhiễu nhẹ cho embedding và ground truth | Giữ nguyên, không sửa tay dữ liệu nguồn; có thể thêm expectation regex để gắn cờ |
| Baseline đạt 1.0 vì `qa.py` tra paper theo title | Không đo được năng lực sinh câu trả lời của LLM | Thêm câu hỏi không chứa title nguyên văn để đo retrieval ngữ nghĩa thật |

## 13. Checklist trước khi nộp

- [ ] Thông tin nhóm và repository chính xác.
- [ ] Phân công khớp với module, artifact và kết quả thực tế.
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [ ] Baseline, corrupted và repaired dùng cùng evaluation set.
- [ ] Bảng metrics khớp với các file trong `data/results/`.
- [ ] Quality/freshness conclusions khớp với `data/quality/`.
- [ ] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [ ] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
