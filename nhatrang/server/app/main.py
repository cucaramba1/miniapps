from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, load_settings
from .db import connect, migrate


def create_app(settings: Settings | None = None, bot=None, clock=None) -> FastAPI:
    settings = settings or load_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.photos_dir).mkdir(parents=True, exist_ok=True)
    conn = connect(settings.db_path)
    migrate(conn)
    conn.close()

    app = FastAPI(title="Нячанг Дом", docs_url=None, redoc_url=None)
    app.state.settings = settings
    if bot is None and settings.bot_token != "test-token":
        from .bot import HttpBotApi
        bot = HttpBotApi(settings.bot_token)
    app.state.bot = bot
    app.state.clock = clock or (lambda: datetime.now(timezone.utc))

    @app.get("/api/health")
    def health():
        return {"ok": True}

    from . import routes_me_flags
    app.include_router(routes_me_flags.router)
    from . import routes_places
    app.include_router(routes_places.router)
    from . import routes_bot_places, routes_pay, routes_realtors_listings, routes_reviews
    app.include_router(routes_realtors_listings.router)
    app.include_router(routes_bot_places.router)
    app.include_router(routes_pay.router)
    app.include_router(routes_reviews.router)

    # Отдаём только allowlist: index.html, js/, shared/. Остальное (server/, data/, docs/) закрыто.
    web = Path(settings.web_dir)
    index = web / "index.html"
    if index.is_file():
        @app.get("/", include_in_schema=False)
        @app.get("/index.html", include_in_schema=False)
        def index_page():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
    if (web / "js").is_dir():
        app.mount("/js", StaticFiles(directory=web / "js"), name="js")
    if (web / "tiles").is_dir():
        app.mount("/tiles", StaticFiles(directory=web / "tiles"), name="tiles")
    if Path(settings.shared_dir).is_dir():
        app.mount("/shared", StaticFiles(directory=settings.shared_dir), name="shared")
    return app
