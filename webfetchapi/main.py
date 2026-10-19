from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from .settings import Settings
from .schemas import SearchRequest, SearchResponse, ResearchRequest, ResearchResponse
from .errors import UpstreamError
from .local_only import LocalOnlyMiddleware
from .search_service import search_only
from .research_service import research
from .ollama_client import list_models


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

    app = FastAPI(title='webfetchapi：本機網路搜尋服務', version='1.0.0', lifespan=lifespan,
                  description='只接受本機呼叫，無呼叫端 API key。/api/search 只需 Tavily 金鑰，模型整合為選用。')
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
                'search_enabled': True, 'research_enabled': config.research_enabled}

    @app.post('/api/search', response_model=SearchResponse, summary='網路搜尋，不呼叫模型')
    async def search(payload: SearchRequest, request: Request):
        return await limited(request.app.state, search_only, payload)

    @app.get('/api/models', summary='選用：校內 Ollama 模型清單')
    async def models(request: Request):
        state = request.app.state
        require_research(state.settings)
        names = ['demo-model'] if state.settings.demo else await list_models(state.client, state.settings)
        return {'models': names, 'mode': 'demo' if state.settings.demo else 'live'}

    @app.post('/api/research', response_model=ResearchResponse, summary='選用：搜尋後由校內模型整合')
    async def run(payload: ResearchRequest, request: Request):
        require_research(request.app.state.settings)
        return await limited(request.app.state, research, payload)

    return app


def require_research(settings):
    if not settings.research_enabled:
        raise UpstreamError('模型整合尚未設定。純搜尋請使用 /api/search；整合需設定 OLLAMA_GATEWAY_API_KEY。',
                            503, 'model_not_configured')


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
