"""Local learning example. No database or migrations are required."""
import os

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
