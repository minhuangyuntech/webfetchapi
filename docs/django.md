# 兩個獨立 Django 範例

兩個 Django 網站均從後端呼叫同機 `webfetchapi`。範例一顯示搜尋內容；範例二再由自己的後端直接呼叫 `http://140.125.35.48:9999` 的 Pi gateway。瀏覽器不直接持有任何 API key。

以下指令均在 **repo 根目錄** 執行，並先依 README 啟動 FastAPI。每個網站使用另一個終端機；所有 `run.py` 都會讀取對應網站 `.env` 的 `DJANGO_PORT` 並綁定 `127.0.0.1`。macOS 與 Raspberry Pi 使用相同 Python 指令。

## 範例一：顯示搜尋片段、正文與來源

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r examples/django_site/requirements.txt
Copy-Item examples/django_site/.env.example examples/django_site/.env
.\.venv\Scripts\python.exe examples/django_site/run.py
```

macOS / Raspberry Pi：

```bash
.venv/bin/python -m pip install -r examples/django_site/requirements.txt
cp examples/django_site/.env.example examples/django_site/.env
.venv/bin/python examples/django_site/run.py
```

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。輸入關鍵字；「擷取網頁正文」預設勾選，取消時只取得搜尋片段。

此網站不呼叫模型、不改寫內容，沒有模型金鑰。template 原樣顯示 API 回傳的文字，保留換行並使用 HTML escaping；來源中的 HTML 標籤會顯示成文字，不會執行。正文擷取失敗或服務截短時，顯示對應狀態。

此網站 `.env`：

```dotenv
WEBFETCHAPI_URL=http://127.0.0.1:8001
DJANGO_PORT=8000
```

## 範例二：搜尋後由 Django 呼叫模型

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r examples/django_summary_site/requirements.txt
Copy-Item examples/django_summary_site/.env.example examples/django_summary_site/.env
notepad examples/django_summary_site/.env
```

macOS / Raspberry Pi：

```bash
.venv/bin/python -m pip install -r examples/django_summary_site/requirements.txt
cp examples/django_summary_site/.env.example examples/django_summary_site/.env
nano examples/django_summary_site/.env
```

在此網站的 `.env` 設定 Pi 金鑰與模型。Tavily key 留在 FastAPI 的 `.env`，不複製到 Django：

```dotenv
WEBFETCHAPI_URL=http://127.0.0.1:8001
DJANGO_PORT=8002
OLLAMA_GATEWAY_URL=http://140.125.35.48:9999
OLLAMA_GATEWAY_API_KEY=你的Pi金鑰
OLLAMA_MODEL=實際安裝的模型名稱
OLLAMA_CONTEXT_TOKENS=8192
OLLAMA_OUTPUT_TOKENS=1024
OLLAMA_SAFETY_TOKENS=512
LLM_DEMO_MODE=0
```

`OLLAMA_CONTEXT_TOKENS` 是希望配置的 context，不代表每個模型或伺服器都能支援該大小。範例還會讀取模型上限；詳細原理見 [context 預算](context-budget.md)。必須能從目前網路連到 Pi，且符合 Pi gateway 的來源網段限制。

填入 key 後，可先查詢模型名稱，不進行推論：

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe examples/django_summary_site/list_models.py
```

```bash
# macOS / Raspberry Pi
.venv/bin/python examples/django_summary_site/list_models.py
```

將其中一個名稱填入 `.env` 的 `OLLAMA_MODEL`，再啟動：

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe examples/django_summary_site/run.py
```

```bash
# macOS / Raspberry Pi
.venv/bin/python examples/django_summary_site/run.py
```

開啟 [http://127.0.0.1:8002](http://127.0.0.1:8002)，輸入關鍵字、希望整理的問題與模型名稱，按「搜尋並彙整」。頁面呈現 context 預算、選取段落、模型回答、實際 token 統計及原始搜尋來源。每次提交是獨立問題，沒有附加既往對話歷史。

流程如下：

1. Django 向 Pi 的 `/api/show` 取得模型資訊，未設定 key 或模型資訊不可用時不進行搜尋。
2. Django 呼叫本機 `/api/search` 取得片段與正文。
3. Django 計算模型輸入預算，選取可以放入的段落。
4. Django 向 Pi 的 `/api/chat` 發出請求，附上 `X-API-Key`、`num_ctx` 與 `num_predict`。
5. 回應失敗時，仍顯示已取得的搜尋資料；輸入放不下時，不呼叫 `/api/chat`。

## 不連外驗證完整流程

根目錄 `.env` 設 `DEMO_MODE=1`；第二個 Django 的 `.env` 設 `LLM_DEMO_MODE=1`。重新啟動程式後，搜尋與模型都使用固定示範資料，不需要任何金鑰。第一個網站仍展示片段和正文；第二個網站仍執行真實的 context 選取演算法，但回答明確標示 DEMO。

兩種 DEMO 設定分開：只開啟 `LLM_DEMO_MODE` 不會把真實搜尋改成離線；只開啟根目錄 `DEMO_MODE` 也不會停用第二個 Django 的真實模型呼叫。

## 在自己的 Django 專案中呼叫搜尋服務

```python
import httpx

with httpx.Client(timeout=90, trust_env=False) as client:
    response = client.post('http://127.0.0.1:8001/api/search', json={
        'query': 'Raspberry Pi 5 用途',
        'max_results': 5,
        'include_body': True,
    })
    response.raise_for_status()
    sources = response.json()['sources']
```

這段程式應在 Django 後端執行。對應完整程式見第一個網站的 `searchdemo/views.py`。若使用 `async def` view，可改用 `httpx.AsyncClient` 與 `await client.post(...)`；同步 `response.json()` 不加 `await`。完整非同步請求處理還需搭配 ASGI 與相容 middleware。

模型相關的 `summarydemo/services.py`、`context_budget.py` 可作為第二步整合參考，與搜尋服務沒有 Python import 相依，只透過 HTTP 取得資料。

兩個範例都不需要資料庫或 `migrate`。預設 `DEBUG=True`、開發用 `SECRET_KEY` 與 `runserver` 僅供本機開發；整合到自己的網站時應沿用該網站的部署設定。勿把外部內容或模型回答標記成 template 的 `safe`。
