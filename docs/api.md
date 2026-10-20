# 搜尋 API 規格

預設 base URL：`http://127.0.0.1:8001`；依根目錄 `.env` 的 `PORT` 調整。`/docs` 提供互動文件。所有端點僅接受本機呼叫，不需呼叫端 API key。

| 方法與路徑 | 功能 |
|---|---|
| `GET /healthz` | 程式啟動狀態，不檢查外部服務 |
| `POST /api/search` | 依關鍵字搜尋，並依要求擷取正文 |

搜尋 API 不提供模型清單或模型推論。v1 的 `/api/models`、`/api/research` 已移除；模型整合放在上層 Django 範例二。

## 請求

```json
{"query":"Raspberry Pi 5 用途","max_results":3,"include_body":true}
```

| 欄位 | 型態與限制 |
|---|---|
| `query` | 必填字串；去除頭尾空白後 1–720 字元 |
| `max_results` | 整數 1–8，預設 5；不接受字串或布林值 |
| `include_body` | 布林值，預設 `true`；`false` 不呼叫 Extract API |

POST 必須為 `Content-Type: application/json`。不接受額外的未定義欄位。

## 回應

以下為結構示意，不是真實查詢結果：

```json
{
  "mode": "live",
  "status": "ok",
  "query": "Raspberry Pi 5 用途",
  "sources": [{
    "id": 1,
    "title": "來源標題",
    "url": "https://example.org/article",
    "content": "搜尋服務提供的片段",
    "published_date": null,
    "body_text": "擷取正文第一段。\n\n第二段。",
    "extraction_status": "ok",
    "extraction_error": null,
    "body_truncated": false,
    "fetched_at": "2026-10-20T00:00:00+00:00"
  }],
  "warnings": [],
  "timings": {"search_seconds": 0.8, "extract_seconds": 1.2, "total_seconds": 2.0},
  "collected_at": "2026-10-20T00:00:00+00:00"
}
```

- `mode`：`live` 真實搜尋／擷取，`demo` 固定離線資料。
- `status`：`ok` 正常；`partial` 有擷取失敗或服務長度截斷；`no_results` 沒有可用搜尋來源。三者都可能是 HTTP 200。
- `content`：搜尋片段，保留 v1 欄位；空白正規化、每筆最多 1,800 字元，合計最多 10,000 字元。
- `body_text`：Tavily Extract 回傳的正文純文字，保留換行與空白；未取得時為 `null`。
- `extraction_status`：`not_requested`、`ok`、`failed`。
- `body_truncated`：是否因本服務長度上限而截短。`false` 只代表本服務未截短，**不保證擷取器已取得原網頁全部內容**。
- `published_date`：來源提供的日期；`fetched_at` 是取得正文的時間；`collected_at` 是本次整理回應的時間，皆不得混為文章發表時間。

正文每來源最多 50,000 字元，所有來源合計最多 160,000 字元。這是傳輸／記憶體上限，不是模型 context 設定；上層網站仍須自行計算模型輸入預算。來源順序保持搜尋結果順序；Extract 批次結果按 URL 對應，不假設回傳順序相同。

只去除清理後重複的網址；不同網址的相似文章仍保留，不以語意相似度自動刪除資料。網址清理移除 fragment 與 `utm_` 參數，僅保留有效 HTTP(S) 連結。

## 部分失敗

搜尋成功但正文擷取逾時、額度不足、格式異常或部分網址失敗時，仍回傳已取得的片段與來源，並附上擷取失敗狀態。上層可顯示錯誤，或明確標示以片段作為備援。Tavily 的原始錯誤字串不直接轉送給呼叫端。

若搜尋本身就失敗，回傳非 200 狀態：

| HTTP | 意義 |
|---|---|
| 400 / 403 | 非本機 Host、來源或跨來源瀏覽器請求 |
| 415 | 未使用 JSON Content-Type |
| 422 | 請求欄位格式／長度有誤 |
| 429 | 本機執行名額已滿，或供應商限制頻率 |
| 502 | 搜尋認證、連線或上游資料格式有誤 |
| 503 | 搜尋額度不足 |
| 504 | 搜尋等待逾時 |

服務錯誤格式為 `{"error":"說明","code":"錯誤代碼"}`；Pydantic 驗證錯誤使用 FastAPI 的 `{"detail":[...]}`。

單 worker 最多 4 個搜尋請求執行中，名額涵蓋搜尋到正文擷取完成的整段流程。搜尋 HTTPX timeout 為 20 秒，Extract 為 45 秒；它們是連線／讀取階段等待限制，不是整體請求的嚴格總秒數上限。上游回應大小另有限制，避免無界累積。
