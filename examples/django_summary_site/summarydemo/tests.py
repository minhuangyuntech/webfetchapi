import copy
import json
from unittest.mock import patch
import httpx
from django.test import SimpleTestCase, Client, override_settings
from .context_budget import BudgetError, context_limit, plan_context, estimate_tokens

REAL_CLIENT = httpx.Client
SOURCES = [{'id': 1, 'title': '來源 A', 'url': 'https://example.org/a', 'content': '搜尋片段',
            'body_text': '樹莓派用途與限制。\n' * 2000, 'extraction_status': 'ok'},
           {'id': 2, 'title': '來源 B', 'url': 'https://example.org/b', 'content': '備援片段',
            'body_text': None, 'extraction_status': 'failed'}]
FORM = {'query': '樹莓派', 'question': '整理用途與限制', 'model': 'test-model', 'max_results': 2}


class BudgetTests(SimpleTestCase):
    def plan(self, **changes):
        args = dict(requested_context=8192, model_max=4096, output_tokens=512, safety_tokens=512)
        return plan_context('樹莓派', '整理用途與限制', SOURCES, **(args | changes))

    def test_caps_context_preserves_original_and_fits_complete_messages(self):
        original = copy.deepcopy(SOURCES)
        plan = self.plan()
        stats = plan['stats']
        self.assertEqual(stats['context_tokens'], 4096)
        self.assertLessEqual(estimate_tokens(plan['messages']) + 512 + 512, 4096)
        self.assertTrue(stats['trimmed'])
        self.assertEqual(stats['used_source_ids'], [1, 2])
        self.assertGreater(stats['omitted_chars'], 0)
        self.assertEqual(SOURCES, original)

    def test_source_ids_and_fallback_are_preserved(self):
        plan = self.plan(requested_context=16384, model_max=16384)
        self.assertEqual(plan['stats']['used_source_ids'], [1, 2])
        self.assertTrue(any(item['source_id'] == 2 and item['content_kind'] == 'snippet' for item in plan['evidence']))

    def test_too_small_and_long_questions_fail_before_chat(self):
        with self.assertRaises(BudgetError):
            self.plan(model_max=1024, output_tokens=1024)
        with self.assertRaises(BudgetError):
            plan_context('查詢', '問'*600, SOURCES, requested_context=2048,
                         model_max=4096, output_tokens=1024, safety_tokens=512)

    def test_context_metadata_is_validated(self):
        self.assertEqual(context_limit({'general.architecture': 'qwen2', 'qwen2.context_length': 32768}), 32768)
        for metadata in ({}, {'x.context_length': True}, {'a.context_length': 4096, 'b.context_length': 2048}):
            with self.assertRaises(BudgetError):
                context_limit(metadata)

    def test_json_escaping_and_multibyte_characters_count_toward_budget(self):
        sources = [SOURCES[0] | {'body_text': ('中文😀"\\\n' * 3000)}]
        plan = plan_context('test', '整理', sources, requested_context=4096,
                            model_max=4096, output_tokens=512, safety_tokens=512)
        self.assertLessEqual(estimate_tokens(plan['messages']), 3072)
        self.assertEqual(json.loads(plan['messages'][1]['content'])['references'], plan['evidence'])


@override_settings(LLM_DEMO_MODE=False, OLLAMA_GATEWAY_API_KEY='fake-gateway-key',
                   OLLAMA_GATEWAY_URL='http://140.125.35.48:9999',
                   WEBFETCHAPI_URL='http://127.0.0.1:8001', OLLAMA_CONTEXT_TOKENS=8192,
                   OLLAMA_OUTPUT_TOKENS=512, OLLAMA_SAFETY_TOKENS=512)
class WebsiteTests(SimpleTestCase):
    def call(self, *, chat_status=200, model_max=4096, sources=None):
        seen = []
        def handler(request):
            seen.append(request)
            if request.url.host == '127.0.0.1':
                self.assertNotIn('x-api-key', request.headers)
                return httpx.Response(200, json={'mode': 'live', 'sources': SOURCES if sources is None else sources,
                                                'warnings': [], 'query': '樹莓派'})
            self.assertEqual(request.headers['x-api-key'], 'fake-gateway-key')
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'model_info': {'test.context_length': model_max}})
            return httpx.Response(chat_status, json={'done': True, 'done_reason': 'stop',
                'message': {'content': '整理內容。[1] <script>bad()</script>'},
                'prompt_eval_count': 1200, 'eval_count': 30})
        with patch('summarydemo.views.httpx.Client',
                   side_effect=lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)):
            response = self.client.post('/', FORM)
        return response, seen

    def test_separate_service_calls_and_context_options(self):
        response, seen = self.call()
        self.assertEqual([r.url.path for r in seen], ['/api/show', '/api/search', '/api/chat'])
        chat = json.loads(seen[-1].content)
        self.assertEqual(chat['options']['num_ctx'], 4096)
        self.assertEqual(chat['options']['num_predict'], 512)
        self.assertFalse(chat['stream'])
        self.assertLessEqual(estimate_tokens(chat['messages']) + 1024, 4096)
        self.assertContains(response, '為符合 context 預算')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertNotContains(response, 'fake-gateway-key')

    def test_model_failure_keeps_sources_and_context_plan(self):
        response, _ = self.call(chat_status=503)
        self.assertContains(response, '模型服務回報 HTTP 503')
        self.assertContains(response, '搜尋服務回傳的來源')
        self.assertContains(response, '來源 A')

    def test_insufficient_context_does_not_call_chat(self):
        response, seen = self.call(model_max=1024)
        self.assertContains(response, '放不下')
        self.assertNotIn('/api/chat', [r.url.path for r in seen])

    def test_no_results_does_not_call_chat(self):
        response, seen = self.call(sources=[])
        self.assertContains(response, '沒有可用搜尋內容')
        self.assertNotIn('/api/chat', [r.url.path for r in seen])

    def test_missing_key_does_not_call_any_service(self):
        with override_settings(OLLAMA_GATEWAY_API_KEY=''), patch('summarydemo.services.request_json') as request:
            self.assertContains(self.client.post('/', FORM), '設定 OLLAMA_GATEWAY_API_KEY')
            request.assert_not_called()

    def test_get_and_csrf_do_not_call_services(self):
        with patch('summarydemo.services.request_json') as request:
            client = Client(enforce_csrf_checks=True)
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(client.post('/', FORM).status_code, 403)
            request.assert_not_called()
