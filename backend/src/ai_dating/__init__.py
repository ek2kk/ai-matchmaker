__version__ = "0.1.0"


def main() -> None:
    import uvicorn

    from ai_dating.app import create_app
    from ai_dating.config import load_settings, require_startup

    settings = load_settings()
    require_startup(settings)
    uvicorn.run(create_app(settings), host=settings.bind_host, port=8000)
