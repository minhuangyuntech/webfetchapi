from unittest.mock import patch
import httpx
from django.test import SimpleTestCase, Client


class WebsiteTests(SimpleTestCase):
    def test_form_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertContains(client.get('/'), '搜尋網路上的參考資料')
        self.assertEqual(client.post('/', {'query': 'Pi', 'max_results': 3}).status_code, 403)

    @patch('searchdemo.views.httpx.Client')
    def test_server_side_request_and_escaped_results(self, client_class):
        upstream = client_class.return_value.__enter__.return_value
        upstream.post.return_value = httpx.Response(200, request=httpx.Request('POST', 'http://127.0.0.1:8001/api/search'),
            json={'mode': 'live', 'query': 'Pi', 'warnings': [], 'timings': {'search_seconds': 0.1},
                  'sources': [{'id': 1, 'title': '<script>alert(1)</script>',
                               'url': 'https://example.org', 'content': '<b>片段</b>',
                               'body_text': '第一段\n\n<script>正文</script>', 'extraction_status': 'ok'}]})
        response = self.client.post('/', {'query': 'Pi', 'max_results': 3, 'include_body': 'on'})
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertContains(response, '第一段\n\n&lt;script&gt;正文&lt;/script&gt;')
        upstream.post.assert_called_once_with('http://127.0.0.1:8001/api/search',
            json={'query': 'Pi', 'max_results': 3, 'include_body': True})

    @patch('searchdemo.views.httpx.Client')
    def test_connection_error_is_readable(self, client_class):
        client_class.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError('unavailable')
        self.assertContains(self.client.post('/', {'query': 'Pi', 'max_results': 3}), '無法連線到本機搜尋服務')
