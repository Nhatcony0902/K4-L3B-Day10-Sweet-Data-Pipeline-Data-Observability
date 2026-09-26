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

> Ghi chú minh bạch: code trong các commit `1135634`, `5723818`, `4ac6bdf` được viết với sự hỗ trợ của trợ lý AI Claude Code (commit có dòng `Co-Authored-By`).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Chốt contract raw/clean/quality trước khi làm song song | Trần Xuân Đức — `testset.py`, `phase1.py`, `corruption_flow.py` | Contract ghi trong `docs/TEAM.md` mục "Contract dùng chung" |
| [Review CP2–CP5 của Đức] | [Module] | [Điền sau khi review] |

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
- **Điều học được:** [Tự viết.]

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

[Tự viết bằng lời của mình.]

## 8. Phân tích kết quả

> Chờ `phase1.py` và `corruption_flow.py` (Trần Xuân Đức) chạy xong để lấy số liệu thật — không điền trước.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      [ ] |       [ ] |      [ ] | [Nhận xét]              |
| `mean_token_f1`      |      [ ] |       [ ] |      [ ] | [Nhận xét]              |
| `judge_accuracy`     |      [ ] |       [ ] |      [ ] | [Nhận xét]              |
| `mean_judge_score`   |      [ ] |       [ ] |      [ ] | [Nhận xét]              |
| Quality checks         |      [ ] |       [ ] |      [ ] | [Nhận xét]              |
| Freshness status       |      [ ] |       [ ] |      [ ] | [Nhận xét]              |

### Kết luận từ số liệu

1. [Data corruption] → [quality/freshness signal thay đổi] → [agent metric thay đổi].
2. [Repair action] → [quality/freshness signal phục hồi] → [agent metric phục hồi hoặc chưa phục hồi].

Corruption nào ảnh hưởng rõ nhất và vì sao?

[Phân tích dựa trên số liệu.]

Kết quả nào khác với kỳ vọng ban đầu?

[Nêu kết quả, giả thuyết và cách đã kiểm tra.]

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. [Điều học được về data pipeline.]
2. [Điều học được về data quality/observability.]
3. [Điều học được về ảnh hưởng của data đến RAG agent.]

### Nếu có thêm thời gian

[Nêu một cải thiện cụ thể, lý do và cách đo cải thiện đó.]

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Long Nhật
**Ngày xác nhận:** [YYYY-MM-DD]
