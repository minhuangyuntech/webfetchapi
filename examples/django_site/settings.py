"""Local learning example. No database or migrations are required."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env', override=False, encoding='utf-8-sig')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'local-learning-example-only-do-not-use-in-production')
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
ROOT_URLCONF = 'urls'
INSTALLED_APPS = ['searchdemo']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware',
              'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware']
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.csrf']},
}]
LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
WEBFETCHAPI_URL = os.environ.get('WEBFETCHAPI_URL', 'http://127.0.0.1:8001').rstrip('/')
DJANGO_PORT = int(os.environ.get('DJANGO_PORT', '8000'))
if not 1024 <= DJANGO_PORT <= 65535:
    raise ValueError('DJANGO_PORT 必須是 1024 到 65535 的整數。')
