"""Read server configuration from the repository's .env, then shell overrides."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'


@dataclass(frozen=True)
class Settings:
    demo: bool = True
    tavily_key: str = ''
    gateway_key: str = ''
    gateway_url: str = 'http://140.125.35.48:9999'
    model: str = ''
    port: int = 8001
    search_timeout: float = 20
    model_timeout: float = 300
    max_active: int = 4

    @property
    def research_enabled(self):
        return self.demo or bool(self.gateway_key)

    @classmethod
    def from_env(cls, env_file=ENV_FILE):
        load_dotenv(env_file, override=False, encoding='utf-8-sig')
        value = os.environ.get('DEMO_MODE', '0')
        if value not in ('0', '1'):
            raise ValueError('DEMO_MODE 必須是 0 或 1。')
        try:
            port = int(os.environ.get('PORT', '8001'))
        except ValueError:
            raise ValueError('PORT 必須是 1024 到 65535 的整數。') from None
        if not 1024 <= port <= 65535:
            raise ValueError('PORT 必須是 1024 到 65535 的整數。')
        result = cls(demo=value == '1', port=port,
            tavily_key=os.environ.get('TAVILY_API_KEY', '').strip(),
            gateway_key=os.environ.get('OLLAMA_GATEWAY_API_KEY', '').strip(),
            gateway_url=os.environ.get('OLLAMA_GATEWAY_URL', cls.gateway_url).strip().rstrip('/'),
            model=os.environ.get('OLLAMA_MODEL', '').strip())
        if not result.demo and not result.tavily_key:
            raise ValueError('請在 .env 設定 TAVILY_API_KEY；離線示範可設定 DEMO_MODE=1。')
        if result.gateway_key:
            try:
                url = urlsplit(result.gateway_url)
                valid = (url.scheme in ('http', 'https') and url.hostname and
                         url.username is None and url.password is None and
                         not url.query and not url.fragment and url.path in ('', '/'))
                _ = url.port
            except ValueError:
                valid = False
            if not valid:
                raise ValueError('OLLAMA_GATEWAY_URL 必須是無帳密、查詢參數與路徑的 HTTP(S) 主機網址。')
        return result
