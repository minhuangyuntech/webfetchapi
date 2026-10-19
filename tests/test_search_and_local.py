import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from webfetchapi.main import create_app
from webfetchapi.settings import Settings
from webfetchapi.local_only import is_loopback
from webfetchapi.__main__ import main


def local_client(settings=None, transport=None, peer='127.0.0.1'):
    return TestClient(create_app(settings or Settings(), transport),
                      base_url='http://127.0.0.1:8001', client=(peer, 51000))


class SearchTests(unittest.TestCase):
    def test_only_search_key_required_and_no_incoming_key(self):
        seen = []

        def provider(request):
            seen.append(request)
            self.assertEqual(request.url, 'https://api.tavily.com/search')
            self.assertEqual(request.headers['authorization'], 'Bearer test-search-key')
            self.assertNotIn('x-api-key', request.headers)
            self.assertEqual(json.loads(request.content)['query'], 'Raspberry Pi')
            return httpx.Response(200, json={'results': [
                {'title': 'Pi', 'url': 'https://example.org/pi', 'content': '資訊片段'}]})

        settings = Settings(demo=False, tavily_key='test-search-key')
        with local_client(settings, httpx.MockTransport(provider)) as c:
            response = c.post('/api/search', json={'query': ' Raspberry Pi ', 'max_results': 3})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'ok')
            self.assertEqual(response.json()['mode'], 'live')
            self.assertEqual(len(response.json()['sources']), 1)
            self.assertEqual(response.json()['timings']['model_seconds'], 0)
            self.assertNotIn('test-search-key', response.text)
            self.assertFalse(c.get('/healthz').json()['research_enabled'])
            self.assertEqual(c.get('/api/models').status_code, 503)
            self.assertEqual(c.post('/api/research', json={
                'target': 'Pi', 'question': '特色'}).json()['code'], 'model_not_configured')
        self.assertEqual(len(seen), 1)

    def test_demo_never_uses_network(self):
        def forbidden(request):
            raise AssertionError('unexpected network request')
        with local_client(transport=httpx.MockTransport(forbidden)) as c:
            body = c.post('/api/search', json={'query': '測試', 'max_results': 2}).json()
            self.assertEqual(body['mode'], 'demo')
            self.assertEqual(len(body['sources']), 2)
            self.assertIn('DEMO', body['warnings'][0])

    def test_empty_results(self):
        with local_client(Settings(demo=False, tavily_key='test'),
                          httpx.MockTransport(lambda r: httpx.Response(200, json={'results': []}))) as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'}).json()['status'], 'no_results')

    def test_request_validation(self):
        with local_client() as c:
            for data in ({}, {'query': '   '}, {'query': 'x' * 721},
                         {'query': 'x', 'max_results': 0}, {'query': 'x', 'max_results': 9},
                         {'query': 'x', 'max_results': '5'}, {'query': 'x', 'max_results': True},
                         {'query': 'x', 'api_key': 'not-an-input'}):
                with self.subTest(data=data):
                    self.assertEqual(c.post('/api/search', json=data).status_code, 422)

    def test_failure_releases_capacity_and_hides_provider_response(self):
        with local_client(Settings(demo=False, tavily_key='test', max_active=1),
                          httpx.MockTransport(lambda r: httpx.Response(401, text='private-key'))) as c:
            for _ in range(2):
                response = c.post('/api/search', json={'query': 'test'})
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()['code'], 'upstream_auth')
                self.assertNotIn('private-key', response.text)
            self.assertEqual(c.app.state.active, 0)


class LocalOnlyTests(unittest.TestCase):
    def test_loopback_addresses(self):
        for host in ('127.0.0.1', '127.0.0.2', '::1', '::ffff:127.0.0.1'):
            self.assertTrue(is_loopback(host))
        for host in ('192.168.1.2', '140.125.35.48', '::ffff:192.168.1.2', 'not-an-ip'):
            self.assertFalse(is_loopback(host))

    def test_remote_peer_cannot_spoof_forwarded_headers(self):
        with local_client(peer='192.168.20.10') as c:
            response = c.post('/api/search', json={'query': 'test'}, headers={
                'X-Forwarded-For': '127.0.0.1', 'Forwarded': 'for=127.0.0.1'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'local_only')

    def test_host_rebinding_rejected(self):
        with local_client() as c:
            for host in ('external.example', '127.0.0.1.external.example', 'user@localhost'):
                with self.subTest(host=host):
                    self.assertEqual(c.get('/healthz', headers={'Host': host}).status_code, 400)
            self.assertEqual(c.get('/healthz', headers={'Host': 'localhost:8001'}).status_code, 200)

    def test_external_and_different_port_browser_origins_rejected(self):
        with local_client() as c:
            for origin in ('https://external.example', 'null', 'http://127.0.0.1:8000'):
                self.assertEqual(c.post('/api/search', json={'query': 'test'},
                                        headers={'Origin': origin}).status_code, 403)
            self.assertEqual(c.post('/api/search', json={'query': 'test'},
                headers={'Origin': 'http://127.0.0.1:8001'}).status_code, 200)

    def test_cross_site_form_and_wrong_content_type_rejected(self):
        with local_client() as c:
            self.assertEqual(c.post('/api/search', json={'query': 'test'},
                headers={'Sec-Fetch-Site': 'cross-site'}).status_code, 403)
            self.assertEqual(c.post('/api/search', content='{"query":"test"}',
                headers={'Content-Type': 'text/plain'}).status_code, 415)
            self.assertEqual(c.post('/api/search', data={'query': 'test'}).status_code, 415)


class ConfigurationTests(unittest.TestCase):
    def test_dotenv_bom_and_shell_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('TAVILY_API_KEY=test-from-file\nPORT=8123\nDEMO_MODE=0\n', encoding='utf-8-sig')
            with patch.dict(os.environ, {}, clear=True):
                config = Settings.from_env(env)
                self.assertEqual(config.port, 8123)
                self.assertEqual(config.tavily_key, 'test-from-file')
                self.assertFalse(config.research_enabled)
            with patch.dict(os.environ, {'PORT': '8124'}, clear=True):
                self.assertEqual(Settings.from_env(env).port, 8124)

    def test_bad_config(self):
        for values in ({'PORT': 'abc'}, {'PORT': '80'}, {'PORT': '65536'},
                       {'DEMO_MODE': 'yes'}, {'DEMO_MODE': '0', 'TAVILY_API_KEY': ''},
                       {'OLLAMA_GATEWAY_API_KEY': 'test', 'OLLAMA_GATEWAY_URL': 'file:///bad'}):
            with self.subTest(values=values), patch.dict(os.environ, {'DEMO_MODE': '1'} | values, clear=True):
                with self.assertRaises(ValueError):
                    Settings.from_env('nonexistent-test.env')

    def test_launcher_enforces_loopback_and_ignores_proxy_headers(self):
        with patch('webfetchapi.__main__.Settings.from_env', return_value=Settings(port=8123)), \
             patch('webfetchapi.__main__.uvicorn.run') as run:
            main()
        self.assertEqual(run.call_args.kwargs['host'], '127.0.0.1')
        self.assertEqual(run.call_args.kwargs['port'], 8123)
        self.assertFalse(run.call_args.kwargs['proxy_headers'])
        self.assertEqual(run.call_args.kwargs['workers'], 1)


if __name__ == '__main__':
    unittest.main()
