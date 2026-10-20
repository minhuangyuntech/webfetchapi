"""Local client checks complement the launcher's fixed loopback binding."""
from ipaddress import ip_address
from urllib.parse import urlsplit
from starlette.datastructures import Headers
from starlette.responses import JSONResponse


def is_loopback(host):
    try:
        address = ip_address(host)
        mapped = getattr(address, 'ipv4_mapped', None)
        return (mapped or address).is_loopback
    except ValueError:
        return False


def origin_parts(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            return None
        return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        return None


class LocalOnlyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        client = scope.get('client')
        # Never read X-Forwarded-For. The supported launcher disables proxy headers.
        if not client or not is_loopback(client[0]):
            await self.reject(scope, receive, send, 403, 'local_only', '此服務僅接受本機連線。')
            return
        headers = Headers(scope=scope)
        hosts = headers.getlist('host')
        origin = origin_parts(f"{scope.get('scheme', 'http')}://{hosts[0]}") if len(hosts) == 1 else None
        if not origin or origin[1] not in ('127.0.0.1', 'localhost', '::1'):
            await self.reject(scope, receive, send, 400, 'invalid_host', '請使用 127.0.0.1 或 localhost 連線。')
            return
        browser_origins = headers.getlist('origin')
        if browser_origins and (len(browser_origins) != 1 or origin_parts(browser_origins[0]) != origin):
            await self.reject(scope, receive, send, 403, 'invalid_origin', '請由同機 Django 後端呼叫此服務。')
            return
        if scope['method'] not in ('GET', 'HEAD', 'OPTIONS') and headers.get('sec-fetch-site') == 'cross-site':
            await self.reject(scope, receive, send, 403, 'cross_site', '不接受外部網站發起的寫入請求。')
            return
        if scope['method'] == 'POST' and scope['path'] == '/api/search':
            if headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                await self.reject(scope, receive, send, 415, 'json_required', '請使用 application/json 傳送 JSON。')
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def reject(scope, receive, send, status, code, message):
        await JSONResponse({'error': message, 'code': code}, status_code=status)(scope, receive, send)
