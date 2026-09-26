# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Trần Xuân Đức |
| MSSV               | 2A202602768 |
| Khóa/Lớp         | K4 |
| Tên nhóm         | Sweet |
| Vai trò chính    | Evaluation, Corruption & Pipeline Integration owner |
| Repository         | https://github.com/Nhatcony0902/K4-L3B-Day10-Sweet-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Evaluation set (CP2) | `src/evaluation/testset.py`: `build_test_set` | Clean DataFrame (`paper_id`, `title`, `summary`, `authors`, `categories`, `published`) | `data/eval/test_set.json` — 10 câu, 4 dạng | Hoàn thành |
| Baseline orchestration (CP3) | `src/pipelines/phase1.py`: `run_phase1_pipeline`, `main` | `Settings`, raw snapshot | `data/clean/papers_clean.{csv,json}`, collection `papers-baseline`, `data/results/baseline_metrics.json`, `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json` | Hoàn thành |
| Reporting (CP3, CP5) | `src/observability/reporting.py`: `generate_phase1_report`, `generate_corruption_report`, `format_comparison_table` | Metrics, quality, freshness, corruption log, answers | `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, bảng so sánh in ra console | Hoàn thành |
| Corruption suite (CP4) | `src/ingestion/corruption.py`: `corrupt_clean_dataframe` | Clean DataFrame | Corrupted DataFrame (21 dòng), `data/results/corruption_log.json` | Hoàn thành |
| Corruption → repair flow (CP5) | `src/pipelines/corruption_flow.py`: `run_corruption_flow_pipeline`, `repair_from_raw_snapshot` | Baseline artifacts, `data/raw/crossref_records.json` | `data/clean/papers_clean_{corrupted,repaired}.*`, `corrupted_metrics.json`, `repaired_metrics.json`, `corrupted/repaired_quality_report.json` | Hoàn thành |

Phần của tôi nhận output từ Phạm Long Nhật (`load_raw_records`, `build_clean_dataframe`, `run_data_quality_checks`, `evaluate_freshness_sla`) và là nơi tích hợp cuối: mọi metric, report và bảng so sánh 3 trạng thái của nhóm đều do hai pipeline của tôi sinh ra. `report/group_report.md` dùng lại các số liệu này.

> Ghi chú minh bạch: code của các phần trên được viết với sự hỗ trợ của trợ lý AI Claude Code; tôi đã chạy lại, kiểm tra artifact và đối chiếu số liệu trước khi viết báo cáo.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Export `evaluate_freshness_sla` ra package `observability` | Nhật — `src/observability/__init__.py` | Corruption flow tính freshness cho corrupted/repaired mà không ghi đè `freshness_report.json` của baseline |
| Review clean schema trước khi làm test set | Nhật — `cleaning.py` | Phát hiện ~12 summary trong raw snapshot bị mất chữ cái đầu ("An extended empirical study on **onnecting**…") — lỗi có sẵn trong `data/raw/crossref_response.json`, không do cleaning; giữ nguyên để không sửa tay dữ liệu nguồn |
| Cấu hình LLM judge chạy được cho cả nhóm | `.env` (không commit) | Chuyển sang Ollama `qwen2.5:3b` local sau khi Gemini bị giới hạn quota (xem mục 6) |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Sinh test set 10 câu phân bổ 3/3/2/2, mỗi câu một paper | `testset.py::build_test_set` | `data/eval/test_set.json` | Lệnh CP2 → `Sinh được 10 câu hỏi test` |
| Nối 6 bước baseline: Ingest → Clean → Index → Testset → Evaluate → GX + Freshness → Report | `phase1.py::run_phase1_pipeline` | `baseline_metrics.json`, `phase1_report.md` | `python script/run_phase1.py` exit 0 |
| Tiêm 6 dạng lỗi có seed, log từng dòng before/after | `corruption.py::corrupt_clean_dataframe` | `corruption_log.json` (20 entry) | Lệnh CP4 → `Corrupted 21 dòng` |
| Evaluate corrupted, repair từ raw, re-evaluate, so sánh 3 trạng thái | `corruption_flow.py` | `corrupted/repaired_metrics.json`, `corruption_report.md` | `python script/run_corruption_flow.py` exit 0, in bảng 3 cột |

Output cụ thể: `data/reports/corruption_report.md` — Retrieval Hit Rate **1.0 → 0.5 → 1.0**, Token F1 **1.0 → 0.727 → 1.0** (recovery 100%); GX gate **PASS → FAIL → PASS** (fail `expect_column_values_to_be_unique` với 4 dòng trùng `paper_id`, và `expect_column_value_lengths_to_be_between` với 3 summary rỗng).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Chứng minh bằng số liệu rằng dữ liệu bẩn làm RAG agent xuống chất lượng **một cách im lặng** (không có exception), rằng lớp observability phát hiện được sự cố, và rằng repair từ nguồn raw khôi phục được hệ thống. Để phép so sánh có ý nghĩa, cả 3 trạng thái phải chạy trên cùng test set, cùng code, cùng cấu hình và kết quả phải tái lập được.

### Cách triển khai

- **Test set:** bỏ trùng `paper_id`, sort theo `published` giảm dần rồi `paper_id` (tất định). Gán dạng câu hỏi xoay vòng `summary → authors → date → categories` cho 10 câu → 3/3/2/2; mỗi câu lấy paper kế tiếp còn đủ dữ liệu cho dạng đó. `ground_truth`: câu đầu của summary (dùng chung `core.utils.first_sentence` với `qa.py`), danh sách tác giả / categories nối `, `, ngày `YYYY-MM-DD`. Wording câu hỏi khớp đúng intent mà `retrieval/qa.py::_extract_answer` nhận diện (`who authored`, `when was`, `what categories`).
- **Corruption:** `numpy.random.default_rng(42)`. Bước 1 bỏ `ceil(20%)` = 5 bài mới nhất. 19 dòng còn lại được hoán vị và chia thành các nhóm **không giao nhau** cho 5 lỗi còn lại (blank 3, noise 3, truncate 3, stale 4, duplicate 2) để quy được tác động về từng loại lỗi. Stale date lùi `published`/`updated` 365 ngày và cộng `age_days`. Sau khi sửa text, tính lại `summary_chars` và `text_for_embedding` (để embedding "nhìn thấy" dữ liệu bẩn), rồi mới nhân bản dòng để bản sao giống hệt bản gốc.
- **Orchestration:** mỗi trạng thái có collection Chroma riêng (`papers-baseline/-corrupted/-repaired`, suy ra từ đường dẫn manifest trong `LocalEmbeddingIndex`), mọi artifact dùng đường dẫn trong `core/config.py`. Test set chỉ sinh lại khi chưa có hoặc `REFRESH_TEST_SET=1`, nên baseline/corrupted/repaired luôn dùng cùng một file.
- **Repair:** `repair_from_raw_snapshot` đọc `data/raw/crossref_records.json` (fallback `crossref_response.json`) và chạy lại đúng `build_clean_dataframe` của pipeline, ghi đè `papers_clean_repaired.*`. Không đọc gì từ dữ liệu corrupted nên chạy lại bao nhiêu lần cũng cho cùng kết quả (idempotent).
- **Report:** bảng metric 3 trạng thái kèm Delta và `Recovery = (Repaired − Corrupted) / (Baseline − Corrupted)`, Hit Rate theo dạng câu hỏi, bảng quality gate, freshness và đoạn phân tích sinh tự động từ số liệu.

### Input, output và contract

| Thành phần | Mô tả |
| ------------------------------ | ------------------------------------------- |
| Input | Clean DataFrame theo `CLEAN_COLUMNS`; `data/raw/crossref_records.json`; `Settings` |
| Output | Test set `{id, question_type, question, ground_truth, ground_truth_doc_ids}`; `*_metrics.json` `{samples, retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score, ragas}`; `*_answers.json`; `corruption_log.json` `{seed, input_rows, output_rows, corruption_counts, entries[{corruption, paper_id, field, before, after}]}`; 2 report Markdown |
| Module phụ thuộc | `ingestion/crossref.py`, `ingestion/cleaning.py`, `observability/quality.py` (Nhật); `retrieval/index.py`, `retrieval/qa.py`, `evaluation/metrics.py` (có sẵn) |
| Module sử dụng output | `script/run_phase1.py`, `script/run_corruption_flow.py`, `report/group_report.md` |
| Điều kiện lỗi cần xử lý | DataFrame thiếu cột hoặc < 10 paper → `ValueError`; paper thiếu authors/categories → bỏ qua sang paper kế; chạy corruption flow khi chưa có baseline → `FileNotFoundError` kèm hướng dẫn chạy `run_phase1.py`; không có raw records → fallback raw response; LLM judge lỗi/hết quota → `metrics.py` fallback heuristic (phải kiểm tra `judge.reasoning` để phát hiện) |

### Cách xác minh

```bash
# CP2
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
# CP3
python script/run_phase1.py
# CP4
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
# CP5
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** 10 câu test; phase 1 sinh CSV + `baseline_metrics.json` + `phase1_report.md`; 6 dạng lỗi được log; bảng 3 trạng thái cho thấy corrupted giảm và repaired phục hồi.
- **Kết quả thực tế:** `Sinh được 10 câu hỏi test` (3 summary / 3 authors / 2 date / 2 categories); phase 1 exit 0 — 24/24 dòng sạch, Hit Rate 1.0, F1 1.0, GX 6/6 pass; `Corrupted 21 dòng` (drop 5, blank 3, noise 3, truncate 3, stale 4, duplicate 2); corruption flow exit 0 với bảng ở mục 8. Kiểm tra thêm: dataset repaired **giống hệt** `papers_clean.json` (trừ `age_days` phụ thuộc ngày chạy), và 10/10 câu trả lời + retrieved doc IDs của repaired trùng baseline.
- **Artifact/log:** `data/eval/test_set.json`, `data/results/*_metrics.json`, `data/results/*_answers.json`, `data/results/corruption_log.json`, `data/quality/{baseline,corrupted,repaired}_quality_report.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau khi làm bẩn dữ liệu cần "sửa" lại để chứng minh hệ thống phục hồi. Cách sửa quyết định việc repair có đáng tin và lặp lại được hay không.
- **Các phương án đã cân nhắc:** (1) đảo ngược từng thay đổi dựa trên `corruption_log.json` (xóa dòng trùng, khôi phục summary/title/ngày cũ); (2) viết các rule "làm sạch dữ liệu bẩn" (dedupe, loại summary rỗng, lọc noise…) chạy trên bản corrupted; (3) dựng lại toàn bộ dataset từ raw snapshot bất biến bằng chính hàm `build_clean_dataframe`.
- **Phương án đã chọn:** (3) — `repair_from_raw_snapshot`.
- **Lý do:** (1) chỉ hoạt động khi biết trước lỗi — ngoài production không có log của sự cố; (1) và (2) cũng không lấy lại được 5 bài bị drop, vì dữ liệu đã mất khỏi bản corrupted. (3) không phụ thuộc bản bẩn, dùng lại đúng code đã qua quality gate ở baseline, và idempotent. Đánh đổi: phải có raw snapshot tin cậy và mất công rebuild toàn bộ (24 dòng thì không đáng kể).
- **Bằng chứng quyết định phù hợp:** repaired dataset == baseline clean dataset (so sánh DataFrame, trừ `age_days`); 24 dòng; GX PASS; Hit Rate và Token F1 phục hồi 100%; answers + retrieved doc IDs trùng baseline 10/10.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Sau khi thêm `GOOGLE_API_KEY`, metrics vẫn giống hệt lúc chưa có LLM. Gọi thử judge báo: `Error calling model 'gemini-2.5-flash' (NOT_FOUND): 404 NOT_FOUND ... This model models/gemini-2.5-flash is no longer available to new users`. Sau khi đổi sang `gemini-3.8-flash`, phase 1 chấm thật 10/10 nhưng phase 2: `429 RESOURCE_EXHAUSTED ... quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: 20`.
- **Lệnh hoặc bước tái hiện:** chạy `run_phase1.py` + `run_corruption_flow.py`, rồi đếm số answer có `judge.reasoning` chứa "Fallback" trong `data/results/*_answers.json` → baseline 0/10, corrupted 7/10, repaired 10/10.
- **Nguyên nhân gốc:** `_judge_answer` trong `metrics.py` bắt mọi exception và âm thầm chuyển sang heuristic Token F1, nên pipeline vẫn exit 0 và in metrics bình thường. Model mặc định trong `config.py` đã ngừng cấp cho user mới, và key thuộc project free tier chỉ có 20 request/ngày/model, trong khi một lượt chạy đủ 3 trạng thái cần 30 lượt judge. Bản thân evaluation cũng có "silent failure" giống hệt dữ liệu.
- **Cách xử lý:** xác định lỗi bằng cách gọi trực tiếp `build_llm(...).with_structured_output(JudgeVerdict)`; không trộn judge của hai model trong cùng bảng (bias so sánh), mà chuyển `.env` sang `LLM_PROVIDER=ollama`, `LLM_MODEL=qwen2.5:3b` chạy local và chạy lại **cả hai** pipeline để 30/30 câu dùng cùng một judge.
- **Cách xác minh sau khi sửa:** cả 2 script exit 0; số answer có "Fallback" = 0 ở cả baseline, corrupted, repaired.
- **Điều học được:** exit code 0 và một con số trong JSON không chứng minh metric đúng — phải kiểm tra nguồn gốc của từng giá trị. Một cơ chế fallback im lặng cần được log/đếm và đưa vào report như một tín hiệu observability.

Phần chưa xử lý triệt để:

- **Phạm vi bị ảnh hưởng:** `judge_accuracy`, `mean_judge_score` ở cả 3 trạng thái.
- **Những gì đã loại trừ:** không phải do fallback (0/30); không phải do dữ liệu — repaired có answers và retrieved doc IDs trùng baseline 10/10 nhưng judge vẫn chấm khác ở `eval_005` (1 vs 3) và `eval_009` (3 vs 2); câu `date` trả lời khớp tuyệt đối vẫn bị 1 điểm vì model cho rằng năm 2026 "không phải ngày xuất bản hợp lệ".
- **Bước tiếp theo:** chạy lại với judge mạnh hơn (Gemini có billing) và/hoặc chấm mỗi câu nhiều lần lấy trung vị; so độ lệch baseline vs repaired phải về 0 khi answers giống nhau.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. `fetch_source_records` đọc snapshot Crossref (hoặc gọi API khi `REFRESH_SOURCE=1`), map mỗi item thành `PaperRecord` và lưu `crossref_records.json` làm mốc lineage. `build_clean_dataframe` chuẩn hóa text, loại dòng thiếu trường bắt buộc, dedupe theo DOI, tính `age_days` và ghép `text_for_embedding` (Title/Authors/Published/Categories/Summary). `LocalEmbeddingIndex.build` embed `text_for_embedding` bằng `all-MiniLM-L6-v2`, ghi vào collection ChromaDB (cosine) kèm metadata, và lưu manifest `data/embeddings/*.json`.
2. Mỗi câu hỏi có `ground_truth_doc_ids` = DOI của paper chứa đáp án. Retrieval hit = DOI đó nằm trong top-k tài liệu `answer_question` trả về → `retrieval_hit_rate`. Answer quality đo bằng Token F1 giữa `answer` và `ground_truth`, và bằng LLM judge (`judge_accuracy`, `mean_judge_score`). Hit rate tách được lỗi "tìm sai tài liệu" khỏi lỗi "trả lời sai": ví dụ `eval_002` ở corrupted trả lời đúng tác giả (F1 = 1.0) nhưng từ một paper khác → hit = False.
3. Quality checks (GX) kiểm tra **cấu trúc/tính hợp lệ** của từng batch: số dòng, not-null, `paper_id` duy nhất, độ dài summary — kết quả pass/fail quyết định gate. Freshness đo **độ cũ** của cả tập (tỷ lệ bài có `age_days` > 180, ngưỡng 25%) — dữ liệu có thể hoàn toàn hợp lệ nhưng lỗi thời. Trong lab, `success` chỉ phản ánh GX, còn freshness là cảnh báo riêng (`is_fresh`).
4. Để mọi chênh lệch metric chỉ đến từ dữ liệu. Nếu test set đổi theo trạng thái (ví dụ sinh lại từ bản corrupted) thì câu hỏi về 5 bài bị drop sẽ biến mất và Hit Rate trông vẫn tốt — che đi đúng sự cố cần đo.
5. Artifact: `papers_clean_repaired.json` (24 dòng, trùng baseline), `repaired_quality_report.json` (GX PASS), `repaired_metrics.json`, `corruption_report.md`. Metric: `retrieval_hit_rate` và `mean_token_f1` trở về bằng baseline (recovery 100%), gate PASS, freshness PASS. Judge metrics chỉ dùng tham khảo vì judge hiện tại không ổn định (mục 6).

## 8. Phân tích kết quả

Nguồn: `data/results/{baseline,corrupted,repaired}_metrics.json`, `data/quality/*_quality_report.json`, `data/reports/corruption_report.md`. Judge: Ollama `qwen2.5:3b`, 30/30 câu chấm thật.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.50 |      1.00 | Giảm 50%, toàn bộ do 5 câu hỏi về 5 bài bị drop; phục hồi 100% |
| `mean_token_f1`      |      1.00 |       0.727 |      1.00 | Giảm ít hơn Hit Rate vì một số câu vẫn trả lời đúng/gần đúng từ paper "sinh đôi" |
| `judge_accuracy`     |      0.70 |       0.40 |      0.60 | Có xu hướng giảm rồi hồi, nhưng baseline ≠ repaired dù answers giống hệt → nhiễu của judge 3B |
| `mean_judge_score`   |      3.6 |       2.9 |      3.7 | Như trên; câu `date` đúng tuyệt đối vẫn bị 1 điểm |
| Quality checks         |      PASS (6/6) |       FAIL (4/6) |      PASS (6/6) | Fail đúng 2 lỗi có thể thấy qua schema: 4 dòng trùng `paper_id`, 3 summary rỗng |
| Freshness status       |      PASS (1/24 = 0.042) |       PASS (5/21 = 0.238) |      PASS (1/24 = 0.042) | Stale ratio tăng 6 lần nhưng vẫn dưới ngưỡng 0.25 → không báo động |

### Kết luận từ số liệu

1. **Drop 5 bài mới nhất + duplicate + blank summary** → GX gate chuyển FAIL (`paper_id` unique: 4 dòng lỗi; summary length: 3 dòng lỗi), stale ratio tăng 0.042 → 0.238 → Hit Rate giảm 1.0 → 0.5, Token F1 1.0 → 0.727, trong khi pipeline RAG vẫn exit 0 và trả lời đủ 10/10 câu (silent failure).
2. **Repair từ raw snapshot** (`build_clean_dataframe` trên `crossref_records.json`) → GX PASS, stale ratio về 0.042, dataset trùng baseline → Hit Rate và Token F1 phục hồi 100%; answers + retrieved IDs trùng baseline 10/10. Judge metrics không về đúng baseline do nhiễu của judge, không phải do dữ liệu.

Corruption nào ảnh hưởng rõ nhất và vì sao?

**Drop latest records** gây ra toàn bộ 5/5 lượt retrieval miss (`eval_001`–`eval_005`). Test set được sinh từ các bài mới nhất, nên mất 20% bài mới nhất nghĩa là mất đúng tài liệu ground truth của một nửa số câu hỏi. Hệ thống không trả lời "không biết" mà lấy paper gần nhất về ngữ nghĩa — ở corpus này là các bài "Advanced Perspectives on …" có nội dung gần giống — nên câu trả lời trông hợp lý nhưng sai nguồn, và có câu còn đúng tình cờ (`eval_002`: tác giả trùng). Đây cũng là lỗi GX **không** bắt được: 21 dòng vẫn nằm trong khoảng 5–5000. Các lỗi còn lại chạm vào paper trong test set (stale date `eval_006`, duplicate `eval_008`/`eval_010`, truncate title `eval_009`) không làm miss retrieval, vì semantic search vẫn tìm được paper qua summary/authors dù title đã bị cắt còn 7 ký tự. Blank summary và inject noise rơi vào các paper không có trong test set nên chỉ lộ ra qua GX, không qua metric của agent.

Kết quả nào khác với kỳ vọng ban đầu?

- **Freshness không báo động** dù có stale date + mất bài mới nhất: 5/21 = 0.238, sát ngưỡng 0.25. Kiểm tra bằng `corrupted_quality_report.json`: 4 dòng bị lùi ngày + 1 dòng vốn đã cũ. Nếu chỉ nhìn freshness SLA sẽ bỏ sót sự cố → cần thêm tín hiệu như `latest_published` (lùi từ 2026-07-22 về 2026-06-11) hoặc ngưỡng row count so với lần chạy trước.
- **Judge không ổn định:** kỳ vọng repaired = baseline vì dữ liệu giống hệt; thực tế judge 0.6 vs 0.7. Đã kiểm tra: answers và retrieved IDs trùng 10/10, chỉ điểm judge khác ở `eval_005`, `eval_009` → nhiễu của model judge 3B.
- **Baseline đạt 1.0 tuyệt đối** vì `qa.py` tra paper theo title trong câu hỏi rồi trả thẳng trường metadata — baseline là trần, không phải thước đo năng lực sinh câu trả lời của LLM.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** tính tái lập quan trọng ngang tính đúng — seed cố định, test set tất định, raw snapshot bất biến và repair idempotent là điều kiện để so sánh 3 trạng thái có ý nghĩa và để người khác chạy lại ra đúng số.
2. **Data quality/observability:** mỗi tín hiệu chỉ bắt được một loại lỗi. GX bắt duplicate và summary rỗng nhưng không bắt được mất 20% bài mới; freshness SLA thì nằm sát ngưỡng. Cần nhiều lớp tín hiệu (schema, volume so với lần trước, độ mới của bản ghi mới nhất) và cả observability cho chính bước evaluation (đếm judge fallback).
3. **Ảnh hưởng đến RAG agent:** lỗi dữ liệu không làm agent "hỏng" mà làm agent trả lời tự tin từ nguồn sai. Chỉ đo chất lượng câu trả lời (Token F1 0.727, có câu đúng tình cờ) sẽ đánh giá thấp mức độ sự cố; phải đo retrieval hit theo ground-truth doc ID mới thấy mất 50%.

### Nếu có thêm thời gian

Thêm **volume/recency check so với baseline** vào quality gate: fail khi row count giảm > 10% hoặc `latest_published` lùi hơn N ngày so với lần chạy trước (lưu trong `baseline_quality_report.json`). Lý do: đây là corruption ảnh hưởng nặng nhất nhưng hiện không có tín hiệu nào báo FAIL. Cách đo: chạy lại corruption flow — kỳ vọng check mới FAIL ở corrupted (21 vs 24 dòng, 2026-06-11 vs 2026-07-22) và PASS ở repaired; đồng thời bổ sung đếm số judge fallback vào `*_metrics.json` để phát hiện evaluation bị suy giảm im lặng.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [X] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Xuân Đức
**Ngày xác nhận:** [2026-09-26]
