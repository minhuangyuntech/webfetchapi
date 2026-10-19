# API 規格

預設 base URL：`http://127.0.0.1:8001`。連接埠依 `.env` 的 `PORT` 而定。互動文件：`/docs`；OpenAPI JSON：`/openapi.json`。

所有端點僅接受本機連線，**不需要呼叫端 API key**。POST 使用 `Content-Type: application/json`。

| 方法與路徑 | 功能 | 對外服務需求 |
|---|---|---|
| `GET /healthz` | 程式與設定狀態 | 無，不檢查外部服務 |
| `POST /api/search` | 搜尋與來源片段 | live 模式需 Tavily key |
| `GET /api/models` | 選用的模型清單 | live 模式需 Pi gateway key |
| `POST /api/research` | 選用的搜尋加模型整理 | live 模式需搜尋與 Pi gateway key |

## `POST /api/search`

請求：

```json
{"query": "Raspberry Pi 5 適合哪些用途？", "max_results": 3}
```

| 欄位 | 型態 | 限制 |
|---|---|---|
| `query` | 字串，必填 | 去除頭尾空白後 1–720 字元 |
| `max_results` | 整數，選填 | 預設 5，範圍 1–8；不接受字串 `"5"` 或布林值 |

未定義的欄位會被拒絕。`max_results` 是上限，清理、去重及略過空片段後的數量可能較少。

回應結構示意，以下為說明用資料：

```json
{
  "mode": "live",
  "status": "ok",
  "query": "Raspberry Pi 5 適合哪些用途？",
  "sources": [
    {
      "id": 1,
      "title": "來源標題",
      "url": "https://example.org/article",
      "content": "搜尋服務提供的內容片段。",
      "published_date": null
    }
  ],
  "warnings": ["回傳搜尋片段與來源網址，未下載網頁全文，也未呼叫模型。"],
  "timings": {"search_seconds": 0.8, "model_seconds": 0, "total_seconds": 0.8},
  "collected_at": "2026-10-19T12:00:00+00:00"
}
```

- `mode`：`live` 為實際搜尋；`demo` 為固定示範資料。
- `status`：有可用來源為 `ok`，沒有可用來源為 `no_results`；兩者皆 HTTP 200。
- `content`：每則最多 1,800 字元，所有片段合計最多 10,000 字元。
- `url`：只保留 HTTP(S) 連結，移除 fragment、`utm_` 參數並去重；服務本身不前往下載這些網址。
- `published_date`：僅當來源有提供時保留；`collected_at` 是本次服務整理資料的 UTC 時間，兩者不同。
- `timings`：單位為秒；純搜尋的 `model_seconds` 固定為 0。

## 錯誤回應

服務處理的錯誤格式：

```json
{"error":"搜尋服務逾時，請稍後再試。","code":"upstream_timeout"}
```

Pydantic 欄位驗證錯誤則遵循 FastAPI 的 `{"detail": [...]}` 格式。

| HTTP | 常見 code | 意義與處理 |
|---|---|---|
| 400 | `invalid_host` | 請使用 `127.0.0.1` 或 `localhost` |
| 403 | `local_only` / `invalid_origin` / `cross_site` | 非本機來源或跨來源瀏覽器呼叫；改由同機 Django 後端呼叫 |
| 415 | `json_required` | 改用 JSON，不用表單或純文字直接傳給 FastAPI |
| 422 | `detail` 驗證資訊，或 `invalid_model` | 檢查字數、整數範圍及選用模型名稱 |
| 429 | `busy` / `upstream_busy` | 本機搜尋／研究合計最多 4 個執行中請求，或搜尋供應商限制頻率；稍後重試 |
| 502 | `upstream_auth` / `connection_failed` / `upstream_error` 等 | 搜尋金鑰、連線、回應格式或上游服務有誤 |
| 503 | `quota_exceeded` / `model_not_configured` | 搜尋額度不足，或尚未啟用選用模型整合 |
| 504 | `upstream_timeout` | 搜尋或模型等待逾時 |

上游原始錯誤內容與金鑰不會放進服務的自訂錯誤回應。網路搜尋等待上限設定為 20 秒；選用模型為 300 秒。HTTPX 的這些值是各階段／讀取等待的 timeout，不是整個流程的嚴格總秒數上限。Django 純搜尋範例使用 30 秒的讀取等待。

搜尋程式不自動重試，以免在不知是否已計費時重複消耗搜尋額度。請依錯誤狀態決定何時重新送出。
