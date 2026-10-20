"""Deterministic fixtures: no Internet calls and no real model inference."""
from .schemas import Source

def demo_sources(target, count):
    rows = [
        ('示範資料 A', '此示範來源說明搜尋對象的基本背景。'),
        ('示範資料 B', '此示範來源補充用途、特色與常見限制。'),
        ('示範資料 C', '開放時間或價格等變動資訊，應到官方來源確認。')]
    return [Source(id=i+1, title=f'{target}：{title}（DEMO）',
                   url=f'https://example.com/demo/{i+1}', content=text)
            for i, (title, text) in enumerate(rows[:count])]

def demo_body(source_id, query):
    return (f'DEMO 正文 {source_id}：{query}\n\n'
            '這是固定離線資料，用來驗證搜尋內容的顯示與後續處理。\n\n'
            '網路資料應保留標題、網址、取得時間與擷取狀態，讓使用者能回到來源檢查。\n\n'
            '不同來源可能有不同日期與觀點；內容相似不代表每一個細節都相同。')
