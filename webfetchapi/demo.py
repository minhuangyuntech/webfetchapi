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

def demo_answer(target):
    return (f'DEMO 示範回應：這不是即時搜尋或真實模型生成。\n\n'
            f'「{target}」的背景整理範例，依據示範資料 A 呈現。[1]\n'
            '實際模式會根據搜尋片段整理內容，並標示可核對的來源。')
