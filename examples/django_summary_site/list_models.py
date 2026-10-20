"""Read model names using only the second Django site's configuration."""
import os
import httpx
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
from django.conf import settings
from summarydemo.services import ServiceError, request_json


if __name__ == '__main__':
    if settings.LLM_DEMO_MODE:
        print('demo-model (DEMO)')
    elif not settings.OLLAMA_GATEWAY_API_KEY:
        raise SystemExit('請先在此 Django 網站的 .env 填入 OLLAMA_GATEWAY_API_KEY。')
    else:
        try:
            with httpx.Client(trust_env=False, follow_redirects=False) as client:
                data = request_json(client, 'GET', settings.OLLAMA_GATEWAY_URL + '/api/tags',
                    label='模型清單服務', timeout=30,
                    headers={'X-API-Key': settings.OLLAMA_GATEWAY_API_KEY})
            models = data.get('models')
            if not isinstance(models, list):
                raise ServiceError('模型清單格式無法解析。')
            names = [item['name'] for item in models if isinstance(item, dict) and isinstance(item.get('name'), str)]
            print('\n'.join(names) if names else '目前沒有可用模型。')
        except ServiceError as exc:
            raise SystemExit(str(exc)) from None
