from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    bot_token: str = "test-token"
    bot_username: str = "nhatrang_dom_bot"
    webhook_secret: str = "test-webhook-secret"
    admin_ids: set[int] = field(default_factory=set)
    db_path: str = str(ROOT / "data" / "app.db")
    photos_dir: str = str(ROOT / "data" / "photos")
    web_dir: str = str(ROOT.parent)            # index.html и js/ (остальное не отдаётся)
    shared_dir: str = str(ROOT.parent.parent / "shared")
    dev_auth: bool = False
    photo_sign_secret: str = "test-photo-secret"
    review_min_chars: int = 150
    review_min_photos: int = 2
    review_max_photos: int = 5
    geo_radius_m: float = 150.0
    geo_max_accuracy_m: float = 150.0
    review_reward_days: int = 3
    review_place_cooldown_days: int = 14
    review_daily_limit: int = 1
    initdata_max_age_s: int = 86400
    # тарифы: гипотезы, правятся здесь
    plan_d3_stars: int = 300
    plan_d3_rub: int = 590
    plan_d7_stars: int = 600
    plan_d7_rub: int = 1190
    photo_url_ttl_s: int = 3600
    tiles_url: str = "/tiles/nhatrang.pmtiles"  # .pmtiles = своя векторная карта, иначе шаблон растровых плиток
    webapp_url: str = ""
    support_text: str = (
        "Вопрос по оплате или возврат Stars: напишите сюда, ответим вручную. "
        "Укажите, что купили и когда."
    )


def _bool(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.split(" #")[0].strip().strip("\"'")
    return out


def load_settings(env: dict[str, str] | None = None) -> Settings:
    # окружение главнее файла server/.env; пустые значения из файла игнорируются
    e = env if env is not None else {**{k: v for k, v in read_env_file(ROOT / ".env").items() if v}, **os.environ}
    s = Settings()
    s.bot_token = e.get("BOT_TOKEN", s.bot_token)
    s.bot_username = e.get("BOT_USERNAME", s.bot_username)
    s.webhook_secret = e.get("WEBHOOK_SECRET", s.webhook_secret)
    s.admin_ids = {int(x) for x in e.get("ADMIN_IDS", "").split(",") if x.strip()}
    s.db_path = e.get("DB_PATH", s.db_path)
    s.photos_dir = e.get("PHOTOS_DIR", s.photos_dir)
    s.web_dir = e.get("WEB_DIR", s.web_dir)
    s.shared_dir = e.get("SHARED_DIR", s.shared_dir)
    s.dev_auth = _bool(e.get("DEV_AUTH"))
    s.photo_sign_secret = e.get("PHOTO_SIGN_SECRET", s.photo_sign_secret)
    s.tiles_url = e.get("TILES_URL", s.tiles_url)
    s.webapp_url = e.get("WEBAPP_URL", s.webapp_url)
    if e.get("APP_ENV", "dev") == "prod":
        if s.dev_auth:
            raise RuntimeError("DEV_AUTH запрещён при APP_ENV=prod")
        for name, default in (
            ("bot_token", "test-token"),
            ("webhook_secret", "test-webhook-secret"),
            ("photo_sign_secret", "test-photo-secret"),
        ):
            if getattr(s, name) == default:
                raise RuntimeError(f"{name} не задан для prod")
    return s
