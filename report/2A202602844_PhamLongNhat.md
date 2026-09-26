# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Phạm Long Nhật |
| MSSV               | 2A202602844 |
| Khóa/Lớp         | K4 |
| Tên nhóm         | Sweet |
| Vai trò chính    | Trưởng nhóm — Data Foundation & Observability owner |
| Repository         | https://github.com/Nhatcony0902/K4-L3B-Day10-Sweet-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Raw ingestion (CP0) | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref `/works` API hoặc snapshot `data/raw/crossref_response.json`; `settings.source_query`, `source_filter`, `max_results`, `refresh_source` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 `PaperRecord`) | Hoàn thành |
| Cleaning & data modeling (CP1) | `src/ingestion/cleaning.py`: `build_clean_dataframe`; `src/core/utils.py`: `clean_markup_text` | `list[PaperRecord]`, `run_date` | DataFrame 24 dòng × 16 cột (`CLEAN_COLUMNS`), `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | Hoàn thành |
| Quality gate & freshness (CP1) | `src/observability/quality.py`: `run_data_quality_checks`, `evaluate_freshness_sla`, `build_freshness_report` | Clean DataFrame, `settings.freshness_threshold_days` | Dict `{success, row_count, failed_checks, checks, freshness}`, `data/quality/<report_name>_quality_report.json` | Hoàn thành |
| Phân công nhóm | `docs/TEAM.md` | Yêu cầu `report/README.md`, `CHECKPOINTS.md` | Bảng phân công theo checkpoint + contract dùng chung | Hoàn thành |

Người dùng output của mình: Trần Xuân Đức dùng `load_raw_records` + `build_clean_dataframe` cho `phase1.py` và bước repair, dùng clean schema cho `testset.py`, và gọi `run_data_quality_checks` / `build_freshness_report` trên dữ liệu baseline, corrupted và repaired.



### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Chốt contract raw/clean/quality trước khi làm song song | Trần Xuân Đức — `testset.py`, `phase1.py`, `corruption_flow.py` | Contract ghi trong `docs/TEAM.md` mục "Contract dùng chung" |
| Review CP2–CP5 của Đức | Trần Xuân Đức — `testset.py`, `corruption.py`, `phase1.py`, `corruption_flow.py` | Test set dùng đúng các cột clean schema (`paper_id`, `authors`, `categories`, `published`, `summary`); corruption flow gọi `run_data_quality_checks` cho corrupted/repaired và dùng `evaluate_freshness_sla` nên không ghi đè `freshness_report.json` của baseline; repair dùng lại `load_raw_records` + `build_clean_dataframe` → `papers_clean_repaired.json` trùng `papers_clean.json` (trừ `age_days`) |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Parse Crossref payload, bỏ thẻ JATS/HTML, chuẩn hóa DOI/tác giả/ngày | `crossref.py::parse_crossref_payload` | 24 `PaperRecord` | Parse snapshot khớp 100% với `crossref_records.json` mẫu |
| Fetch có retry 429/5xx + fallback snapshot, mặc định dùng snapshot | `crossref.py::fetch_source_records` | 2 raw artifact trong `data/raw/` | Lệnh CP0 → `Đã tải 24 bài báo`; mock 429 và mất mạng → fallback 24 bài |
| Làm sạch, tính `age_days`, dedupe, sinh `text_for_embedding` | `cleaning.py::build_clean_dataframe` | `data/clean/papers_clean.{csv,json}` | Lệnh CP1 → `Clean thành công 24 dòng` |
| Quality gate GX 1.x + freshness SLA | `quality.py::run_data_quality_checks` | `data/quality/test_quality_report.json` | Lệnh CP1 → `Quality check status = True` |

Output cụ thể: `data/quality/test_quality_report.json` — 6 expectation (row count, 3 × not-null, unique `paper_id`, độ dài `summary`) đều pass; freshness: 1/24 bài quá 180 ngày (`stale_ratio = 0.0417` ≤ 0.25) → `is_fresh = true`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Đưa metadata bài báo từ Crossref vào pipeline dưới dạng có thể tái lập (raw được bảo toàn làm lineage anchor), làm sạch thành một bảng có schema cố định cho embedding, và chặn dữ liệu xấu/cũ trước khi vào vector store.

### Cách triển khai

- **Ingestion:** mỗi item Crossref được map sang `PaperRecord`. Title lấy phần tử đầu không rỗng; abstract bỏ tiêu đề `<title>`/`<jats:title>` và toàn bộ thẻ JATS/HTML, giải mã entity, gộp khoảng trắng; ngày lấy theo thứ tự ưu tiên `published → published-print → published-online → issued → created`, hỗ trợ `date-parts` thiếu tháng/ngày. Item thiếu DOI/title/abstract/ngày bị loại, DOI trùng giữ bản đầu.
- **Fetch:** mặc định đọc snapshot để kết quả ổn định; `REFRESH_SOURCE=1` mới gọi API (timeout 30s, tối đa 3 lần, backoff mũ, tôn trọng `Retry-After`). API lỗi → đọc snapshot. Raw response chỉ được ghi đè khi API trả về ≥ 1 record hợp lệ.
- **Cleaning:** chuẩn hóa text và list (bỏ phần tử rỗng/trùng), parse ngày với `errors="coerce"`, loại dòng thiếu `paper_id`/`title`/`summary` hoặc ngày không hợp lệ, `age_days = (run_date − published).days`, dedupe `paper_id` giữ bản `updated` mới nhất, sort theo `published` giảm dần. `text_for_embedding` gồm 5 dòng `Title / Authors / Published / Categories / Summary`.
- **Quality:** GX 1.x ephemeral context (`add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe`), một `ExpectationSuite` gồm 4 nhóm expectation bắt buộc, `batch.validate(suite)`. `success` chỉ phản ánh GX; freshness là tín hiệu cảnh báo riêng (`is_fresh = stale_ratio ≤ 25%`).

### Input, output và contract

| Thành phần | Mô tả |
| ------------------------------ | ------------------------------------------- |
| Input | Crossref `/works` JSON (`message.items[]`) hoặc snapshot; `run_date` cho cleaning; clean DataFrame cho quality |
| Output | `PaperRecord` (11 trường); DataFrame `CLEAN_COLUMNS` (16 cột, `published`/`updated` dạng `YYYY-MM-DD`); dict quality + JSON report |
| Module phụ thuộc | `core/config.py` (paths, threshold), `core/utils.py` (`clean_markup_text`, `write_json`) |
| Module sử dụng output | `retrieval/index.py` (`text_for_embedding`, `authors_joined`, `categories_joined`, …), `evaluation/testset.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, `observability/reporting.py` |
| Điều kiện lỗi cần xử lý | HTTP 429/5xx, mất mạng, JSON lỗi, API trả 0 record; abstract có thẻ JATS/tiêu đề; ngày thiếu tháng/ngày hoặc không hợp lệ; DOI trùng/khác hoa-thường; tác giả tổ chức chỉ có `name` |

### Cách xác minh

```bash
cd src
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```

- **Kết quả mong đợi:** `Đã tải 24 bài báo`, `Clean thành công 24 dòng`, `Quality check status = True`.
- **Kết quả thực tế:** đúng cả 3 chuỗi. Thêm kiểm thử dữ liệu bẩn: summary rỗng + `paper_id` trùng + title null → GX `success = False` với 3 expectation fail; giả lập 8/24 bài `age_days = 400` → `is_fresh = False`.
- **Artifact/log:** `data/raw/crossref_records.json`, `data/clean/papers_clean.json`, `data/quality/test_quality_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Gọi Crossref API thật trả về 24 bài nhưng cả 24 đều không có `subject` (categories rỗng) và có bài không phải tiếng Anh. Nếu mỗi lần chạy đều gọi API thì snapshot bị ghi đè, dữ liệu thay đổi theo ngày, và câu hỏi dạng `categories` trong test set không có ground truth.
- **Các phương án đã cân nhắc:** (1) luôn gọi API, chỉ fallback khi lỗi; (2) gọi API nhưng lưu sang file khác; (3) mặc định dùng snapshot, chỉ gọi API khi bật `REFRESH_SOURCE=1`.
- **Phương án đã chọn:** (3).
- **Lý do:** ưu tiên reproducibility — baseline, corrupted và repaired phải chạy trên cùng dữ liệu và cùng test set; vẫn giữ đường gọi API thật (retry + fallback) qua cờ đã có sẵn trong `core/config.py`, không đổi đường dẫn artifact.
- **Bằng chứng quyết định phù hợp:** chạy lệnh CP0 mặc định → `git status` không đổi `data/raw/`; bật `refresh_source` → 24 bài thật, 24/24 thiếu categories; mock 429/offline → fallback 24 bài.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** sau khi chạy lệnh CP0, `git status` báo `M data/raw/crossref_records.json`, `M data/raw/crossref_response.json`; records mới có `categories: []` ở cả 24 bài và summary bắt đầu bằng chữ `Abstract`.
- **Lệnh hoặc bước tái hiện:** chạy lệnh kiểm tra CP0 khi phiên bản đầu của `fetch_source_records` luôn gọi API.
- **Nguyên nhân gốc:** (1) Crossref API hiện không trả trường `subject`; hàm luôn gọi API nên ghi đè snapshot mẫu. (2) Abstract thật chứa `<title>Abstract</title>` / `<jats:title>Abstract</jats:title>`; regex bỏ thẻ chỉ bỏ thẻ, giữ lại nội dung tiêu đề.
- **Cách xử lý:** khôi phục snapshot bằng `git checkout -- data/raw/`; thêm nhánh `REFRESH_SOURCE` (mặc định đọc snapshot) và dòng `REFRESH_SOURCE=` trong `.env.example`; `clean_markup_text` bỏ cả khối `<(jats:)?title>…</(jats:)?title>` trước khi bỏ thẻ.
- **Cách xác minh sau khi sửa:** lệnh CP0 → 24 bài, `git diff -- data/` rỗng; parse response thật → chỉ còn 1 summary bắt đầu bằng "Abstract -" (là chữ tác giả viết, không phải thẻ).
- **Điều học được:** cách hoạt đông của luồng pineline end-to-end
## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**
1.Để dữ liệu đi từ nguồn Crossref đến khi sẵn sàng làm vector index, pipeline thường trải qua các giai đoạn chính sau:Thu thâph->Làm sạch,chuân hoá->Kiểm soát chất lượng->baseline pineline
2.quy trình:Benchmark Test Set->Ground-truth Document IDs->Đo lường Retrieval Quality
3.Quality Checks (Kiểm soát chất lượng): Tập trung vào việc đảm bảo dữ liệu đầu vào và các bước xử lý dữ liệu (như ở Bước 4 với Great Expectations) tuân thủ đúng các quy tắc về định dạng và giá trị (trong bài: số dòng 5–5000; `paper_id`, `title`, `text_for_embedding` không null; `paper_id` không trùng; `summary` ≥ 30 ký tự). Nó đảm bảo rằng dữ liệu "đúng" về mặt nội dung trước khi được đưa vào hệ thống vector.
Freshness Monitoring (Giám sát độ tươi): Tập trung vào tính thời gian của dữ liệu. Trong bài, nó đo tỷ lệ bài có `age_days > 180`; nếu tỷ lệ này vượt 25% thì gắn cờ `is_fresh = False`. Freshness là cảnh báo riêng, không làm quality gate FAIL. Mục tiêu là đảm bảo hệ thống luôn sử dụng dữ liệu mới nhất, tránh tình trạng "lỗi thời" dù dữ liệu có thể vẫn đảm bảo về mặt định dạng (quality).
4.Baseline: Cung cấp kết quả nền tảng (chưa bị tác động) để làm thước đo chuẩn.
Corrupted: Khi chạy cùng bộ Test Set này trên dữ liệu đã bị tiêm lỗi, sự suy giảm về chỉ số (metrics) sẽ phản ánh chính xác mức độ ảnh hưởng tiêu cực của lỗi đó đối với khả năng truy vấn (retrieval) và chất lượng trả lời.
Repaired: Sau khi áp dụng các biện pháp phục hồi, chạy lại chính bộ Test Set đó giúp em định lượng được hiệu quả thực sự của quy trình phục hồi: liệu hệ thống đã khôi phục lại gần bằng mức Baseline ban đầu hay chưa.
5.Metric chính: Nhóm em dựa vào `retrieval_hit_rate` (paper ground truth có nằm trong top-4 không) và `mean_token_f1` (độ khớp câu trả lời với ground truth); `judge_accuracy`/`mean_judge_score` chỉ để tham khảo vì judge `qwen2.5:3b` chấm không ổn định. Kết quả: Hit Rate 1.0 → 0.5 → 1.0, Token F1 1.0 → 0.727 → 1.0, tức phục hồi 100%. Phục hồi được coi là thành công khi các chỉ số này trên tập Repaired cải thiện đáng kể so với tập Corrupted và tiệm cận trở lại mức của Baseline.
Artifact đối chiếu:
Kết quả so sánh: `data/reports/corruption_report.md` và `data/results/{baseline,corrupted,repaired}_metrics.json`.
Pipeline artifacts: Các file dữ liệu sạch đã qua phục hồi (output của quá trình repair).
Báo cáo quality gate (`data/quality/{corrupted,repaired}_quality_report.json`): Các thông báo trạng thái hoặc kết quả kiểm định của Great Expectations sau khi dữ liệu đã được xử lý/phục hồi, cho thấy các "Data Corruption" trước đó đã được giải quyết hoặc đưa về ngưỡng cho phép.

## 8. Phân tích kết quả

Nguồn: `data/results/{baseline,corrupted,repaired}_metrics.json`, `data/quality/{baseline,corrupted,repaired}_quality_report.json`, `data/results/corruption_log.json` (lượt chạy 2026-09-26 của Trần Xuân Đức; judge Ollama `qwen2.5:3b`). Góc nhìn của mình: owner của quality gate và freshness — đánh giá lớp observability đã bắt được gì và bỏ sót gì.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.00 | 0.50 | 1.00 | Giảm một nửa trong khi pipeline vẫn exit 0 — đây là thiệt hại mà quality gate phải báo trước |
| `mean_token_f1`      | 1.00 | 0.727 | 1.00 | Giảm ít hơn Hit Rate: có câu vẫn đúng tình cờ từ paper sai (`eval_002`: F1 = 1.0 nhưng hit = False) |
| `judge_accuracy`     | 0.70 | 0.40 | 0.60 | Repaired ≠ baseline dù dữ liệu giống hệt → nhiễu của judge 3B, không dùng làm bằng chứng về dữ liệu |
| `mean_judge_score`   | 3.6 | 2.9 | 3.7 | Như trên |
| Quality checks         | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Fail `paper_id` unique (4 dòng) và `summary` length (3 dòng) |
| Freshness status       | PASS (1/24 = 0.042) | PASS (5/21 = 0.238) | PASS (1/24 = 0.042) | Stale ratio tăng gần 6 lần nhưng vẫn dưới ngưỡng 0.25 → không cảnh báo |

**Độ phủ của quality gate trên 6 kịch bản corruption:**

| Corruption (số dòng) | Tín hiệu bắt được? | Lý do |
|---|---|---|
| `duplicate_rows` (2) | ✅ `expect_column_values_to_be_unique` — 4 dòng lỗi | Mỗi bản nhân đôi làm cả 2 dòng cùng `paper_id` bị tính là unexpected |
| `blank_summary` (3) | ✅ `expect_column_value_lengths_to_be_between` — 3 dòng lỗi | Chuỗi rỗng **không phải null** nên `not_null` vẫn pass; chỉ check độ dài ≥ 30 bắt được |
| `drop_latest_records` (5) | ❌ | 21 dòng vẫn nằm trong 5–5000; freshness chỉ đo tỷ lệ bài cũ, không đo `latest_published` (lùi từ 2026-07-22 về 2026-06-11) |
| `stale_date` (4) | ❌ | 5/21 = 0.238 < 0.25; cần thêm 1 dòng stale (6/21 = 0.286) mới FAIL |
| `truncate_title` (3) | ❌ | Title 7 ký tự vẫn not-null, không có check độ dài title |
| `inject_noise` (3) | ❌ | Summary có noise vẫn dài ≥ 30 ký tự |

→ Gate bắt được **2/6** loại lỗi, và bỏ sót đúng loại gây thiệt hại lớn nhất.

### Kết luận từ số liệu

1. **Duplicate + blank summary** → GX gate PASS → FAIL (unique: 4 dòng, summary length: 3 dòng) → gate phát hiện đúng sự cố dù agent vẫn trả lời đủ 10/10 câu; song song đó **drop 5 bài mới nhất** → không check nào FAIL → `retrieval_hit_rate` 1.0 → 0.5 (cả 5 câu miss `eval_001`–`eval_005` đều hỏi về 5 bài bị drop).
2. **Repair từ `data/raw/crossref_records.json` bằng chính `build_clean_dataframe`** → GX PASS 6/6, stale ratio về 0.042, dataset repaired giống hệt baseline (24 dòng, so sánh mọi cột trừ `age_days`) → `retrieval_hit_rate` và `mean_token_f1` phục hồi 100%; judge metrics không về đúng baseline do nhiễu của judge, không do dữ liệu.

Corruption nào ảnh hưởng rõ nhất và vì sao?

`drop_latest_records`: toàn bộ 5/5 lượt retrieval miss đến từ đây vì test set được sinh từ các bài mới nhất. Với vai trò owner quality gate, điểm đáng chú ý là đây lại là lỗi **không có tín hiệu nào báo**: row count check có biên quá rộng (5–5000) so với quy mô 24 dòng, còn freshness dạng tỷ lệ lại **tăng** khi mất bài mới (mẫu số giảm) nhưng vẫn chưa chạm ngưỡng. Hai lỗi mà gate bắt được (duplicate, blank summary) rơi vào các paper ngoài test set hoặc không làm miss retrieval.

Kết quả nào khác với kỳ vọng ban đầu?

- Kỳ vọng `stale_date` làm freshness FAIL; thực tế 0.238, sát ngưỡng 0.25. Kiểm tra `corrupted_quality_report.json`: `stale_rows = 5` (4 dòng bị lùi 365 ngày + 1 dòng vốn đã 182 ngày), `total_rows = 21`. Kết luận: một ngưỡng tỷ lệ duy nhất dễ bị "vừa dưới ngưỡng"; cần thêm tín hiệu tuyệt đối như `latest_published` so với lần chạy trước.
- Kỳ vọng `not_null` bắt được summary rỗng; thực tế không, vì chuỗi `""` khác `null`. Check độ dài mới là check hiệu quả cho completeness của text.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1.Data Pipeline: Một pipeline dữ liệu không chỉ là quá trình chuyển đổi (ETL), mà còn cần sự xuyên suốt từ khâu thu thập bản gốc, làm sạch, cho đến việc kiểm soát chất lượng (observability gate) để đảm bảo dữ liệu đầu vào luôn đáng tin cậy cho các bước tiếp theo.
2.Data Quality & Observability: Khả năng giám sát (observability) giúp ta phát hiện sớm các bất thường trong dữ liệu thông qua các ngưỡng kiểm tra tự động (như Great Expectations). Điều này giúp phân biệt rõ giữa dữ liệu "đúng định dạng" và dữ liệu "chứa thông tin chính xác/còn mới".
3.Ảnh hưởng của Data đến RAG Agent: Chất lượng của dữ liệu ảnh hưởng trực tiếp đến khả năng retrieval (truy xuất) và chất lượng phản hồi của RAG. Dữ liệu bị lỗi (corrupted) làm `retrieval_hit_rate` giảm từ 1.0 xuống 0.5 dù pipeline không báo lỗi, và chỉ khi có quy trình phục hồi (repair) hiệu quả, hệ thống mới có thể duy trì được độ ổn định so với baseline.

### Nếu có thêm thời gian

Em sẽ thêm vào quality gate một kiểm tra so với lần chạy trước: FAIL khi số dòng giảm quá 10% hoặc `latest_published` bị lùi. Lý do: lỗi `drop_latest_records` gây toàn bộ 5 lượt retrieval miss nhưng hiện không có check nào bắt được. Cách đo: chạy lại `run_corruption_flow.py`, kỳ vọng check mới FAIL ở corrupted (21 so với 24 dòng; 2026-06-11 so với 2026-07-22) và PASS ở baseline/repaired.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [X] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Long Nhật
**Ngày xác nhận:** [2026-09-26]
