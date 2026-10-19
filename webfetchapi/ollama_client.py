from .http_utils import read_json
from .errors import UpstreamError

async def list_models(client, settings):
    data = await read_json(client, 'GET', settings.gateway_url + '/api/tags',
        label='模型服務', timeout=15,
        headers={'X-API-Key': settings.gateway_key})
    models = data.get('models')
    if not isinstance(models, list):
        raise UpstreamError('模型服務未提供有效模型清單。')
    return [m['name'] for m in models if isinstance(m, dict)
            and isinstance(m.get('name'), str)]

async def chat(client, settings, model, messages):
    data = await read_json(client, 'POST', settings.gateway_url + '/api/chat',
        label='模型服務', limit=4_000_000, timeout=settings.model_timeout,
        headers={'X-API-Key': settings.gateway_key},
        json={'model': model, 'messages': messages, 'stream': False,
              'keep_alive': '5m', 'options': {'temperature': 0.2, 'num_predict': 1200}})
    message = data.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    if data.get('error') or data.get('done') is not True or not isinstance(content, str) or not content.strip():
        raise UpstreamError('模型未提供完整有效回答。')
    return content.strip()[:20_000], data
