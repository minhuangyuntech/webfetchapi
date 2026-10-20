from datetime import datetime, timezone
from .errors import UpstreamError
from .http_utils import read_json
from .search_client import safe_url


async def extract_bodies(client, settings, sources):
    """Ask Tavily to extract selected search results; never call an LLM."""
    try:
        data = await read_json(client, 'POST', 'https://api.tavily.com/extract',
            label='正文擷取服務', timeout=settings.extract_timeout, limit=4_000_000,
            headers={'Authorization': f'Bearer {settings.tavily_key}'},
            json={'urls': [s.url for s in sources], 'extract_depth': 'basic',
                  'format': 'text', 'include_images': False, 'include_usage': True})
        # Omit query/chunks_per_source: request body content, not query-specific snippets.
        if not isinstance(data.get('results'), list):
            raise UpstreamError('正文擷取服務未提供有效 results 欄位。')
    except UpstreamError as exc:
        for source in sources:
            source.extraction_status = 'failed'
            source.extraction_error = exc.message
        return

    # Batch results can be out of order. Never associate them by array position.
    by_url = {}
    for row in data['results']:
        if isinstance(row, dict):
            url = safe_url(row.get('url', ''))
            body = row.get('raw_content')
            if url and isinstance(body, str) and body.strip() and url not in by_url:
                by_url[url] = body
    remaining = settings.max_total_body_chars
    for source in sources:
        body = by_url.get(source.url)
        if body is None:
            source.extraction_status = 'failed'
            source.extraction_error = '此來源未取得可用正文，請查看搜尋片段或原始網址。'
            continue
        keep = min(len(body), settings.max_body_chars, remaining)
        if keep == 0:
            source.extraction_status = 'failed'
            source.extraction_error = '此次正文總長度已達上限。'
            source.body_truncated = True
            continue
        source.body_text = body[:keep]
        source.body_truncated = keep < len(body)
        source.extraction_status = 'ok'
        source.fetched_at = datetime.now(timezone.utc).isoformat()
        remaining -= keep
