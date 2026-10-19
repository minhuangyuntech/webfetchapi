from datetime import datetime, timezone
from time import perf_counter
from . import demo, search_client
from .schemas import SearchResponse, Timings


async def search_only(client, settings, request):
    started = perf_counter()
    if settings.demo:
        sources = demo.demo_sources(request.query, request.max_results)
        warnings = ['DEMO：固定示範資料，未呼叫網際網路搜尋服務。']
    else:
        sources = await search_client.search(client, settings, request.query, request.max_results)
        warnings = ['回傳搜尋片段與來源網址，未下載網頁全文，也未呼叫模型。']
    elapsed = round(perf_counter() - started, 3)
    return SearchResponse(mode='demo' if settings.demo else 'live',
        status='ok' if sources else 'no_results', query=request.query, sources=sources,
        warnings=warnings, timings=Timings(search_seconds=elapsed, total_seconds=elapsed),
        collected_at=datetime.now(timezone.utc).isoformat())
