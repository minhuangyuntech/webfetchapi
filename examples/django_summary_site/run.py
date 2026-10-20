import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
from django.conf import settings
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    execute_from_command_line(['manage.py', 'runserver', f'127.0.0.1:{settings.DJANGO_PORT}', *sys.argv[1:]])
