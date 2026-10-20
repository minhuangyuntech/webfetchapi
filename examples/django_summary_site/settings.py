import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env', override=False, encoding='utf-8-sig')


def integer(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError(f'{name} 必須是整數。') from None
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} 必須介於 {minimum} 與 {maximum}。')
    return value


SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'local-learning-example-only-do-not-use-in-production')
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
ROOT_URLCONF = 'urls'
INSTALLED_APPS = ['summarydemo']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware',
              'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.csrf']}}]
LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
WEBFETCHAPI_URL = os.environ.get('WEBFETCHAPI_URL', 'http://127.0.0.1:8001').rstrip('/')
DJANGO_PORT = integer('DJANGO_PORT', 8002, 1024, 65535)
OLLAMA_GATEWAY_URL = os.environ.get('OLLAMA_GATEWAY_URL', 'http://140.125.35.48:9999').rstrip('/')
OLLAMA_GATEWAY_API_KEY = os.environ.get('OLLAMA_GATEWAY_API_KEY', '').strip()
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', '').strip()
OLLAMA_CONTEXT_TOKENS = integer('OLLAMA_CONTEXT_TOKENS', 8192, 1024, 131072)
OLLAMA_OUTPUT_TOKENS = integer('OLLAMA_OUTPUT_TOKENS', 1024, 64, 8192)
OLLAMA_SAFETY_TOKENS = integer('OLLAMA_SAFETY_TOKENS', 512, 256, 8192)
if os.environ.get('LLM_DEMO_MODE', '0') not in ('0', '1'):
    raise ValueError('LLM_DEMO_MODE 必須是 0 或 1。')
LLM_DEMO_MODE = os.environ.get('LLM_DEMO_MODE', '0') == '1'
try:
    gateway = urlsplit(OLLAMA_GATEWAY_URL)
    valid_gateway = (gateway.scheme in ('http', 'https') and gateway.hostname and
        gateway.username is None and gateway.password is None and
        not gateway.query and not gateway.fragment and gateway.path in ('', '/'))
    _ = gateway.port
except ValueError:
    valid_gateway = False
if not valid_gateway:
    raise ValueError('OLLAMA_GATEWAY_URL 必須是無帳密、查詢參數與路徑的 HTTP(S) 主機網址。')
