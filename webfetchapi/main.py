from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from .settings import Settings
from .schemas import SearchRequest, SearchResponse
from .errors import UpstreamError
from .local_only import LocalOnlyMiddleware
from .search_service import search_only


def create_app(settings=None, transport=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings or Settings.from_env()
        app.state.active = 0
        async with httpx.AsyncClient(transport=transport, trust_env=False,
                follow_redirects=False, timeout=20,
                limits=httpx.Limits(max_connections=12, max_keepalive_connections=6)) as client:
            app.state.client = client
            yield

    app = FastAPI(title='webfetchapi：本機網路內容搜尋服務', version='2.0.0', lifespan=lifespan,
                  description='依關鍵字搜尋並擷取網頁正文；只接受本機呼叫，不需呼叫端 API key。')
    app.add_middleware(LocalOnlyMiddleware)

    @app.exception_handler(UpstreamError)
    async def upstream_error(request, exc):
        return JSONResponse(status_code=exc.status, content={'error': exc.message, 'code': exc.code})

    @app.get('/', include_in_schema=False)
    async def index():
        return RedirectResponse('/docs')

    @app.get('/healthz')
    async def health(request: Request):
        config = request.app.state.settings
        return {'status': 'ok', 'mode': 'demo' if config.demo else 'live',
                'search_enabled': True, 'body_extraction_enabled': True}

    @app.post('/api/search', response_model=SearchResponse, summary='網路搜尋與正文擷取')
    async def search(payload: SearchRequest, request: Request):
        return await limited(request.app.state, search_only, payload)

    return app


async def limited(state, function, payload):
    # One worker/event loop: no await between checking and incrementing.
    if state.active >= state.settings.max_active:
        raise UpstreamError('處理名額已滿，請稍後再試。', 429, 'busy')
    state.active += 1
    try:
        return await function(state.client, state.settings, payload)
    finally:
        state.active -= 1


app = create_app()
