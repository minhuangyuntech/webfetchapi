import re
from datetime import datetime, timezone
from time import perf_counter
from . import demo, ollama_client, search_client
from .errors import UpstreamError
from .prompts import build_messages
from .schemas import ResearchResponse, Timings

async def research(client, settings, request):
    start = perf_counter()
    query = f'{request.target} {request.question}'
    if settings.demo:
        return ResearchResponse(mode='demo', status='ok', query=query,
            answer=demo.demo_answer(request.target),
            sources=demo.demo_sources(request.target, request.max_results),
            citations=[1], warnings=['DEMO：固定示範資料，未連線搜尋與模型服務。'],
            timings=Timings(total_seconds=round(perf_counter()-start, 3)),
            collected_at=datetime.now(timezone.utc).isoformat(), model='demo-model')

    # Validate the configured/selected model before spending search credits.
    models = await ollama_client.list_models(client, settings)
    model = request.model or settings.model
    if not model or model not in models:
        raise UpstreamError('請從可用清單選擇模型，或正確設定 OLLAMA_MODEL。', 422, 'invalid_model')
    t = perf_counter()
    sources = await search_client.search(client, settings, query, request.max_results)
    search_seconds = perf_counter()-t
    status, answer, warnings, citations = 'ok', '', [], []
    model_seconds = 0
    if not sources:
        status, answer = 'no_results', '找不到可用的搜尋片段，請調整搜尋對象或問題。'
    else:
        t = perf_counter()
        try:
            answer, metadata = await ollama_client.chat(client, settings, model, build_messages(request, sources))
            numbers = sorted(set(int(v) for v in re.findall(r'\[(\d+)\]', answer)))
            allowed = {s.id for s in sources}
            citations = [n for n in numbers if n in allowed]
            if any(n not in allowed for n in numbers):
                warnings.append('回答含不存在的來源編號，請核對原文。')
            if not citations:
                warnings.append('模型未提供可核對的來源編號，請核對來源內容。')
            if metadata.get('done_reason') == 'length':
                warnings.append('回答達到生成長度上限，內容可能不完整。')
        except UpstreamError as exc:
            status, answer = 'partial', '搜尋已完成，但模型暫時無法整合。可先查閱下方來源。'
            warnings.append(exc.message)
        model_seconds = perf_counter()-t
    warnings.append('依搜尋片段整理；引用編號有效不代表內容已完成事實查核。')
    return ResearchResponse(mode='live', status=status, query=query, answer=answer,
        sources=sources, citations=citations, warnings=warnings,
        timings=Timings(search_seconds=round(search_seconds, 3),
                        model_seconds=round(model_seconds, 3),
                        total_seconds=round(perf_counter()-start, 3)),
        collected_at=datetime.now(timezone.utc).isoformat(), model=model)
