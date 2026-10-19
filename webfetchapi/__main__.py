"""Supported entry point: python -m webfetchapi. Always bind loopback."""
import uvicorn
from .main import create_app
from .settings import Settings


def main():
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    uvicorn.run(create_app(settings), host='127.0.0.1', port=settings.port,
                proxy_headers=False, forwarded_allow_ips='', workers=1,
                server_header=False, ws='none')


if __name__ == '__main__':
    main()
