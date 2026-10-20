import re
import httpx
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .forms import ResearchForm
from .services import ServiceError, model_limit, search, make_plan, summarize
from .context_budget import BudgetError


@require_http_methods(['GET', 'POST'])
def index(request):
    form = ResearchForm(request.POST if request.method == 'POST' else None,
        initial={'model': 'demo-model' if settings.LLM_DEMO_MODE else settings.OLLAMA_MODEL})
    context = {'form': form, 'llm_demo': settings.LLM_DEMO_MODE}
    if request.method == 'POST' and form.is_valid():
        fields = form.cleaned_data
        try:
            with httpx.Client(trust_env=False, follow_redirects=False) as client:
                # Validate model/context before spending search credits.
                maximum = model_limit(client, fields['model'])
                result = search(client, fields['query'], fields['max_results'])
                context['result'] = result
                if not result['sources']:
                    raise ServiceError('沒有可用搜尋內容，因此未呼叫模型。')
                plan = make_plan(fields['query'], fields['question'], result['sources'], maximum)
                context['plan'] = plan
                reply = summarize(client, fields['model'], plan)
                context['reply'] = reply
                warnings = []
                numbers = {int(n) for n in re.findall(r'\[(\d{1,6})\]', reply['answer'])}
                allowed = set(plan['stats']['used_source_ids'])
                if not numbers or not numbers <= allowed:
                    warnings.append('回答缺少可用引用，或引用了未送入模型的來源；請核對下方證據。')
                if reply['done_reason'] == 'length':
                    warnings.append('模型達到輸出長度上限，回答可能不完整。')
                count = reply.get('prompt_eval_count')
                if type(count) is int and count > plan['stats']['input_budget']:
                    warnings.append('模型回報的輸入 token 超出預算；請調高安全預留或使用匹配的 tokenizer。')
                context['model_warnings'] = warnings
        except (ServiceError, BudgetError) as exc:
            context['error'] = str(exc)
    return render(request, 'summarydemo/index.html', context)
