import json
from urllib.parse import urlsplit
import httpx
from django.conf import settings
from .context_budget import BudgetError, context_limit, plan_context


class ServiceError(Exception):
    pass


def request_json(client, method, url, *, label, timeout, headers=None, payload=None):
    try:
        with client.stream(method, url, headers=headers, json=payload, timeout=timeout) as response:
            if response.status_code != 200:
                raise ServiceError(f'{label}回報 HTTP {response.status_code}，請檢查設定或稍後再試。')
            parts, size = [], 0
            for part in response.iter_bytes():
                size += len(part)
                if size > 4_000_000:
                    raise ServiceError(f'{label}回應超過大小限制。')
                parts.append(part)
            data = json.loads(b''.join(parts))
            if not isinstance(data, dict):
                raise ValueError('expected object')
            return data
    except httpx.TimeoutException:
        raise ServiceError(f'{label}逾時，請稍後再試。') from None
    except httpx.HTTPError:
        raise ServiceError(f'無法連線到{label}，請確認網路與服務設定。') from None
    except (ValueError, UnicodeError):
        raise ServiceError(f'{label}回應的 JSON 格式無法解析。') from None


def model_limit(client, model):
    if settings.LLM_DEMO_MODE:
        return 8192
    if not settings.OLLAMA_GATEWAY_API_KEY:
        raise ServiceError('請在第二個 Django 網站的 .env 設定 OLLAMA_GATEWAY_API_KEY。')
    data = request_json(client, 'POST', settings.OLLAMA_GATEWAY_URL + '/api/show',
        label='模型資訊服務', timeout=30,
        headers={'X-API-Key': settings.OLLAMA_GATEWAY_API_KEY}, payload={'model': model})
    info = data.get('model_info')
    if not isinstance(info, dict):
        raise ServiceError('模型資訊未包含 model_info，無法確認 context 長度。')
    return context_limit(info)


def search(client, query, max_results):
    data = request_json(client, 'POST', settings.WEBFETCHAPI_URL + '/api/search',
        label='網路內容搜尋服務', timeout=90,
        payload={'query': query, 'max_results': max_results, 'include_body': True})
    sources = data.get('sources')
    if not isinstance(sources, list) or len(sources) > 8:
        raise ServiceError('搜尋結果格式無法解析。')
    ids = set()
    for source in sources:
        try:
            url = urlsplit(source['url'])
            valid = (type(source['id']) is int and source['id'] > 0 and source['id'] not in ids and
                isinstance(source['title'], str) and isinstance(source['content'], str) and
                (source.get('body_text') is None or isinstance(source['body_text'], str)) and
                url.scheme in ('http', 'https') and url.hostname and
                url.username is None and url.password is None)
            ids.add(source['id'])
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise ServiceError('搜尋來源格式或網址無法解析。')
    return data


def make_plan(query, question, sources, model_max):
    return plan_context(query, question, sources,
        requested_context=settings.OLLAMA_CONTEXT_TOKENS, model_max=model_max,
        output_tokens=settings.OLLAMA_OUTPUT_TOKENS, safety_tokens=settings.OLLAMA_SAFETY_TOKENS)


def summarize(client, model, plan):
    stats = plan['stats']
    if settings.LLM_DEMO_MODE:
        first_id = stats['used_source_ids'][0]
        return {'answer': f'DEMO：這是固定示範回應，未呼叫大語言模型。選取的參考段落來自來源 [{first_id}]。',
                'mode': 'demo', 'prompt_eval_count': None, 'eval_count': None, 'done_reason': 'demo'}
    data = request_json(client, 'POST', settings.OLLAMA_GATEWAY_URL + '/api/chat',
        label='模型服務', timeout=300, headers={'X-API-Key': settings.OLLAMA_GATEWAY_API_KEY},
        payload={'model': model, 'messages': plan['messages'], 'stream': False, 'keep_alive': '5m',
                 'options': {'num_ctx': stats['context_tokens'], 'num_predict': stats['output_tokens'],
                             'temperature': 0.2}})
    message = data.get('message')
    answer = message.get('content') if isinstance(message, dict) else None
    if data.get('error') or data.get('done') is not True or not isinstance(answer, str) or not answer.strip():
        raise ServiceError('模型未提供完整有效回答；原始搜尋內容仍保留在下方。')
    return {'answer': answer, 'mode': 'live',
            'prompt_eval_count': data.get('prompt_eval_count'), 'eval_count': data.get('eval_count'),
            'done_reason': data.get('done_reason')}
