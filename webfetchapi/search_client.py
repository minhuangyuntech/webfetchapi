from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from .schemas import Source
from .http_utils import read_json
from .errors import UpstreamError

def safe_url(raw):
    try:
        p = urlsplit(str(raw))
        if len(str(raw)) > 2048 or p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            return None
        if any(ord(c) < 32 for c in raw):
            return None
        # Only use links for display. This program never downloads these URLs.
        params = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                  if not k.lower().startswith('utm_')]
        normalized = urlunsplit((p.scheme, p.netloc.lower(), p.path or '/', urlencode(params), ''))
        return normalized if len(normalized) <= 2048 else None
    except (ValueError, TypeError):
        return None

def normalize_results(items, max_results):
    sources, seen, remaining = [], set(), 10_000
    if not isinstance(items, list):
        raise UpstreamError('搜尋結果格式無法解析。')
    for item in items:
        if not isinstance(item, dict):
            continue
        url = safe_url(item.get('url', ''))
        content = item.get('content')
        if not url or url in seen or not isinstance(content, str) or not content.strip():
            continue
        content = ' '.join(content.split())[:min(1800, remaining)]
        if not content:
            break
        title = item.get('title')
        date = item.get('published_date')
        sources.append(Source(id=len(sources)+1,
            title=(title if isinstance(title, str) else url)[:240],
            url=url, content=content,
            published_date=date[:80] if isinstance(date, str) else None))
        seen.add(url)
        remaining -= len(content)
        if len(sources) >= max_results or remaining <= 0:
            break
    return sources

async def search(client, settings, query, count):
    data = await read_json(client, 'POST', 'https://api.tavily.com/search',
        label='搜尋服務', timeout=settings.search_timeout,
        headers={'Authorization': f'Bearer {settings.tavily_key}'},
        json={'query': query, 'search_depth': 'basic', 'max_results': count,
              'include_answer': False, 'include_raw_content': False,
              'auto_parameters': False, 'topic': 'general', 'include_usage': True})
    if not isinstance(data.get('results'), list):
        raise UpstreamError('搜尋服務未提供有效 results 欄位。')
    return normalize_results(data['results'], count)
