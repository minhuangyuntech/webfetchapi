"""Read server configuration from the repository's .env, then shell overrides."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'


@dataclass(frozen=True)
class Settings:
    demo: bool = True
    tavily_key: str = ''
    port: int = 8001
    search_timeout: float = 20
    extract_timeout: float = 45
    max_body_chars: int = 50_000
    max_total_body_chars: int = 160_000
    max_active: int = 4

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
            tavily_key=os.environ.get('TAVILY_API_KEY', '').strip())
        if not result.demo and not result.tavily_key:
            raise ValueError('請在 .env 設定 TAVILY_API_KEY；離線示範可設定 DEMO_MODE=1。')
        return result
