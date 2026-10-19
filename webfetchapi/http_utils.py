import json
import httpx
from .errors import UpstreamError

async def read_json(client, method, url, *, label, limit=2_000_000, **kwargs):
    """Bound the response body and do not disclose upstream response text or keys."""
    try:
        async with client.stream(method, url, **kwargs) as response:
            if response.status_code != 200:
                status = response.status_code
                if status == 429:
                    raise UpstreamError(f'{label}忙碌或超過頻率限制，請稍後再試。', 429, 'upstream_busy')
                if status in (432, 433):
                    raise UpstreamError(f'{label}額度不足，請檢查服務後台。', 503, 'quota_exceeded')
                if status in (401, 403):
                    raise UpstreamError(f'{label}認證或來源網段設定有誤。', 502, 'upstream_auth')
                if status == 404:
                    raise UpstreamError(f'{label}找不到指定模型或 API 路徑。', 502, 'upstream_not_found')
                raise UpstreamError(f'{label}回報服務錯誤（HTTP {status}）。')
            parts, size = [], 0
            async for part in response.aiter_bytes():
                size += len(part)
                if size > limit:
                    raise UpstreamError(f'{label}回應超過大小限制。')
                parts.append(part)
            data = json.loads(b''.join(parts))
            if not isinstance(data, dict):
                raise ValueError('expected object')
            return data
    except httpx.TimeoutException as exc:
        raise UpstreamError(f'{label}逾時，請稍後再試。', 504, 'upstream_timeout') from exc
    except httpx.HTTPError as exc:
        raise UpstreamError(f'無法連線到{label}。', 502, 'connection_failed') from exc
    except (ValueError, UnicodeError) as exc:
        raise UpstreamError(f'{label}回傳的資料格式無法解析。') from exc
