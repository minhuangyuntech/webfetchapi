from datetime import datetime, timezone
from time import perf_counter
from . import demo, search_client
from .extract_client import extract_bodies
from .schemas import SearchResponse, Timings


async def search_only(client, settings, request):
    started = perf_counter()
    sources = (demo.demo_sources(request.query, request.max_results) if settings.demo else
               await search_client.search(client, settings, request.query, request.max_results))
    search_seconds = perf_counter() - started
    warnings = ['DEMO：固定示範資料，未連線到搜尋與擷取服務。'] if settings.demo else []
    extraction_started = perf_counter()
    if request.include_body and sources:
        if settings.demo:
            for source in sources:
                source.body_text = demo.demo_body(source.id, request.query)
                source.extraction_status = 'ok'
                source.fetched_at = datetime.now(timezone.utc).isoformat()
        else:
            await extract_bodies(client, settings, sources)
        if any(source.extraction_status == 'failed' for source in sources):
            warnings.append('部分正文擷取失敗，仍保留搜尋片段與來源網址。')
        if any(source.body_truncated for source in sources):
            warnings.append('部分正文達到服務傳輸長度限制；請查看 body_truncated。')
    elif not request.include_body:
        warnings.append('此次只取得搜尋片段，未要求擷取正文。')
    extract_seconds = perf_counter() - extraction_started if request.include_body and sources else 0
    partial = any(s.extraction_status == 'failed' or s.body_truncated for s in sources)
    status = 'no_results' if not sources else 'partial' if partial else 'ok'
    return SearchResponse(mode='demo' if settings.demo else 'live', status=status,
        query=request.query, sources=sources, warnings=warnings,
        timings=Timings(search_seconds=round(search_seconds, 3), extract_seconds=round(extract_seconds, 3),
                        total_seconds=round(perf_counter() - started, 3)),
        collected_at=datetime.now(timezone.utc).isoformat())
