# Django 的模型 context 預算

這一層位於第二個 Django 網站的 `summarydemo/context_budget.py`。搜尋服務只回傳內容，不需要知道模型名稱、tokenizer、context 長度或提示詞。

## 先區分三種長度

| 長度 | 意義 |
|---|---|
| 模型宣告上限 | Pi 轉送 `/api/show` 的 `model_info` 中，模型架構對應的 `*.context_length` |
| 本次要求的 context | `.env` 的 `OLLAMA_CONTEXT_TOKENS`，送入 Ollama 的 `options.num_ctx` |
| 實際配置與可用空間 | 受模型、Ollama 執行設定、模板與硬體資源影響，需在伺服器端確認 |

程式取前兩者的較小值。模型沒有可辨識的 context 資訊時，停止本次流程，不猜測它的最大容量。這個模型上限不等於當下已配置的 KV cache；設定值應使用伺服器已驗證可運作的容量，可在 AI 主機以 `ollama ps` 查看載入模型的 context。

## 預算公式

```text
C = min(設定要求的 context, 模型宣告的 context 上限)
B = C - 回答預留 O - 安全預留 S

估計完整輸入 E <= B
亦即：E + O + S <= C
```

例如 `C=8192`、`O=1024`、`S=512`，輸入預算為 `6656`。這個預算還要容納 system 指令、使用者問題、來源標題／網址／編號、JSON 格式與正文，不是全部都能放正文。

`.env` 設定：

```dotenv
OLLAMA_CONTEXT_TOKENS=8192
OLLAMA_OUTPUT_TOKENS=1024
OLLAMA_SAFETY_TOKENS=512
```

模型請求使用相同的數值：

```python
options = {
    'num_ctx': plan['stats']['context_tokens'],
    'num_predict': plan['stats']['output_tokens'],
    'temperature': 0.2,
}
```

`num_predict` 限制生成 token；部分推理模型的思考也可能占用生成預算，過小時可能沒有完整最終回答。應依模型實測調整，不只增加輸入 context。

## 估算方法與實際限制

為了讓範例不必下載特定模型的 tokenizer，預設採用 **UTF-8 位元組數加固定訊息開銷** 作為保守估算。計算的是已組好的每則 message 內容，包含 JSON escape 與來源資訊，不使用「一個中文字等於一個 token」的假設。

這通常比常見 tokenizer 的實際 token 數大，但**不是所有 tokenizer／chat template 的數學上界，也不是精確計數保證**。安全預留用來吸收模板、特殊 token 等不確定性。模型回應後會顯示 `prompt_eval_count` 與 `eval_count`；這些是事後統計，不能取代送出前的估算，也無法單憑它們保證伺服器沒有截斷輸入。

若需要精確控制，應將 `estimate_tokens()` 換成與部署模型**相同版本、相同正規化規則與聊天模板**的 tokenizer，對完整 messages 套用實際 chat template 再計數，包括 assistant 起始標記。不能用任意另一個模型的 tokenizer 作為精確計數。本範例保留獨立計數函式，方便後續替換。

## 放不下時如何處理

1. 優先使用 `body_text`；正文取得失敗時使用 `content` 搜尋片段，並保留 `content_kind`。
2. 按原文字行分段，過長的行再切成最多 800 字元的片段。
3. 用英文詞與中文字元 bigram 比對問題、關鍵字，進行簡單的相關性排序。這是可閱讀的基礎規則，不是語意搜尋或資訊完整性保證。
4. 第一輪為各來源保留一份可用容量，先考慮各來源的第一個相關段落；後續輪流加入其他段落。每加一段都重新計算完整訊息預算。容量過小時仍可能無法涵蓋每個來源，頁面會列出未納入的來源。
5. 剩餘空間不足時，二分搜尋可容納的字元前綴；不切斷 Unicode 字元。不足以容納有用文字就略過。
6. 指令與問題本身就超量，或沒有任何可用證據能放入時，不呼叫模型，顯示原因。

原始搜尋結果不被修改。頁面列出送入／省略的字元數、納入／未納入的來源、實際送入的段落。**字元數與 token 數分開顯示。** 模型提示詞也明確指出只取得選取段落，不能宣稱讀完全部文章。

這種方法適合針對問題整理資訊；若使用者要求完整逐篇摘要，單次段落篩選可能漏掉重點。可在上層 Django 延伸成分段摘要再合併，但每個模型請求都必須重新計算預算，且需保留來源與未處理段落狀態。

## 證據與輸出

段落保留來源編號、標題、網址與段落編號，要求模型以 `[1]` 等方式引用。若回答沒有可核對的來源，或引用未送入的來源編號，頁面提示核對。這項檢查不等於事實查核。

外部網頁內容以資料處理，提示詞要求忽略其中的指令；JSON 序列化只是結構區分，不能保證免除提示注入。此範例不讓模型執行工具或任意網址請求。

官方參考：[Ollama context](https://docs.ollama.com/context-length)、[生成參數](https://docs.ollama.com/modelfile)、[Chat 回應中的 token 統計](https://docs.ollama.com/api/chat)。
