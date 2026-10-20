import asyncio
import json
import unittest
from dataclasses import replace
import httpx
from fastapi.testclient import TestClient
from webfetchapi.main import create_app
from webfetchapi.settings import Settings
from webfetchapi.search_client import normalize_results, safe_url

LIVE = Settings(demo=False, tavily_key='fake-search-key')
ROWS = [{'title': '來源 A', 'url': 'https://example.org/a', 'content': '片段 A'},
        {'title': '來源 B', 'url': 'https://example.org/b', 'content': '片段 B'}]


def client_for(handler, settings=LIVE):
    return TestClient(create_app(settings, httpx.MockTransport(handler)),
                      base_url='http://127.0.0.1', client=('127.0.0.1', 50000))


class ExtractionTests(unittest.TestCase):
    def test_extracts_bodies_in_correct_order_without_model_calls(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(request.url.host, 'api.tavily.com')
            self.assertEqual(request.headers['authorization'], 'Bearer fake-search-key')
            if request.url.path == '/search':
                return httpx.Response(200, json={'results': ROWS})
            payload = json.loads(request.content)
            self.assertNotIn('query', payload)
            self.assertNotIn('chunks_per_source', payload)
            self.assertEqual(payload['urls'], [row['url'] for row in ROWS])
            return httpx.Response(200, json={'results': [
                {'url': ROWS[1]['url'], 'raw_content': '正文 B\n\n保留段落'},
                {'url': ROWS[0]['url'], 'raw_content': '正文 A\n  保留空白'}]})
        with client_for(handler) as c:
            response = c.post('/api/search', json={'query': '測試'}).json()
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['sources'][0]['body_text'], '正文 A\n  保留空白')
        self.assertEqual(response['sources'][1]['body_text'], '正文 B\n\n保留段落')
        self.assertEqual(response['sources'][0]['content'], '片段 A')
        self.assertEqual(len(calls), 2)

    def test_failed_and_unrelated_results_do_not_replace_sources(self):
        def handler(request):
            return httpx.Response(200, json={'results': ROWS}) if request.url.path == '/search' else httpx.Response(200,
                json={'results': [{'url': ROWS[1]['url'], 'raw_content': '正文 B'},
                                  {'url': 'https://other.example', 'raw_content': 'unrelated'}],
                      'failed_results': [{'url': ROWS[0]['url'], 'error': 'private details'}]})
        with client_for(handler) as c:
            response = c.post('/api/search', json={'query': 'test'})
        data = response.json()
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(data['sources'][0]['extraction_status'], 'failed')
        self.assertEqual(data['sources'][0]['content'], '片段 A')
        self.assertEqual(data['sources'][1]['body_text'], '正文 B')
        self.assertNotIn('private details', response.text)

    def test_extract_error_preserves_search_snippets(self):
        for status in (401, 429, 433, 500):
            def handler(request):
                return httpx.Response(200, json={'results': ROWS}) if request.url.path == '/search' else httpx.Response(status)
            with self.subTest(status=status), client_for(handler) as c:
                response = c.post('/api/search', json={'query': 'test'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], 'partial')
                self.assertEqual(len(response.json()['sources']), 2)

    def test_body_limits_are_reported(self):
        def handler(request):
            return httpx.Response(200, json={'results': ROWS}) if request.url.path == '/search' else httpx.Response(200,
                json={'results': [{'url': row['url'], 'raw_content': '字'*100} for row in ROWS]})
        with client_for(handler, replace(LIVE, max_body_chars=60, max_total_body_chars=80)) as c:
            data = c.post('/api/search', json={'query': 'test'}).json()
        self.assertEqual(data['status'], 'partial')
        self.assertEqual([len(s['body_text']) for s in data['sources']], [60, 20])
        self.assertTrue(all(s['body_truncated'] for s in data['sources']))

    def test_search_errors_and_malformed_responses(self):
        for upstream, expected in ((401, 502), (429, 429), (433, 503), (500, 502)):
            with self.subTest(upstream=upstream), client_for(lambda r: httpx.Response(upstream, text='secret')) as c:
                response = c.post('/api/search', json={'query': 'test'})
                self.assertEqual(response.status_code, expected)
                self.assertNotIn('secret', response.text)
        with client_for(lambda r: httpx.Response(200, text='{broken')) as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'}).status_code, 502)
        with client_for(lambda r: httpx.Response(200, content=b'x'*2_000_001)) as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'}).status_code, 502)

    def test_search_timeout_and_extract_timeout(self):
        def timeout(request):
            raise httpx.ReadTimeout('private', request=request)
        with client_for(timeout) as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'}).status_code, 504)
        def extract_timeout(request):
            return httpx.Response(200, json={'results': ROWS}) if request.url.path == '/search' else timeout(request)
        with client_for(extract_timeout) as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'}).json()['status'], 'partial')

    def test_url_deduplication_and_unsafe_links(self):
        rows = ROWS + [ROWS[0] | {'url': ROWS[0]['url'] + '?utm_source=test#top'}]
        self.assertEqual(len(normalize_results(rows, 8)), 2)
        for url in ('javascript:alert(1)', 'file:///etc/passwd', 'https://user:pass@example.org', 'https://[bad'):
            self.assertIsNone(safe_url(url))


class ConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_slot_held_until_extraction_finishes(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            if request.url.path == '/extract':
                entered.set()
                await release.wait()
                return httpx.Response(200, json={'results': []})
            return httpx.Response(200, json={'results': ROWS})
        app = create_app(replace(LIVE, max_active=1), httpx.MockTransport(handler))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=('127.0.0.1', 1)),
                                         base_url='http://127.0.0.1') as c:
                pending = asyncio.create_task(c.post('/api/search', json={'query': 'test'}))
                await asyncio.wait_for(entered.wait(), 3)
                self.assertEqual((await c.post('/api/search', json={'query': 'test'})).status_code, 429)
                release.set()
                self.assertEqual((await pending).status_code, 200)
                self.assertEqual(app.state.active, 0)
