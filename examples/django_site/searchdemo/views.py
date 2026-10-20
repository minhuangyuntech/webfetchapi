from urllib.parse import urlsplit
import httpx
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .forms import SearchForm


@require_http_methods(['GET', 'POST'])
def index(request):
    form = SearchForm(request.POST if request.method == 'POST' else None)
    context = {'form': form}
    if request.method == 'POST' and form.is_valid():
        try:
            # This runs on the Django server, not in browser JavaScript.
            # Both Python services run on the same computer/network namespace.
            with httpx.Client(timeout=90, trust_env=False) as client:
                response = client.post(f'{settings.WEBFETCHAPI_URL}/api/search',
                    json={'query': form.cleaned_data['query'],
                          'max_results': form.cleaned_data['max_results'],
                          'include_body': form.cleaned_data['include_body']})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get('sources'), list):
                raise ValueError('invalid response')
            # Defense in depth for clickable links; template autoescaping stays enabled.
            for source in data['sources']:
                if not isinstance(source, dict) or urlsplit(source.get('url', '')).scheme not in ('http', 'https'):
                    raise ValueError('invalid source URL')
            context['result'] = data
        except httpx.TimeoutException:
            context['error'] = '搜尋逾時，請稍後再試。'
        except httpx.HTTPStatusError as exc:
            context['error'] = f'搜尋服務回報 HTTP {exc.response.status_code}；請檢查 FastAPI 終端機與設定。'
        except httpx.RequestError:
            context['error'] = '無法連線到本機搜尋服務。請先啟動 webfetchapi，並確認連接埠一致。'
        except (ValueError, TypeError):
            context['error'] = '搜尋服務回傳的格式無法解析。'
    return render(request, 'searchdemo/index.html', context)
