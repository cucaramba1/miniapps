from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect
from app.main import create_app

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def make_init_data(user_id: int, bot_token: str, auth_date: int | None = None,
                   first_name: str = "Тест") -> str:
    auth_date = int(time.time()) if auth_date is None else auth_date
    fields = {"auth_date": str(auth_date), "query_id": "AAH",
              "user": json.dumps({"id": user_id, "first_name": first_name}, ensure_ascii=False)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t


class FakeBotApi:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def _rec(self, name, **kw):
        self.calls.append((name, kw))

    def send_message(self, chat_id, text, reply_markup=None):
        self._rec("send_message", chat_id=chat_id, text=text, reply_markup=reply_markup)

    def answer_callback(self, callback_id, text):
        self._rec("answer_callback", callback_id=callback_id, text=text)

    def create_invoice_link(self, title, description, payload, stars):
        self._rec("create_invoice_link", title=title, payload=payload, stars=stars)
        return f"https://t.me/$invoice_{payload}"

    def answer_pre_checkout(self, query_id, ok, error=None):
        self._rec("answer_pre_checkout", query_id=query_id, ok=ok, error=error)

    def refund_star_payment(self, user_id, charge_id):
        self._rec("refund_star_payment", user_id=user_id, charge_id=charge_id)

    def named(self, name):
        return [kw for n, kw in self.calls if n == name]


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "t.db"), photos_dir=str(tmp_path / "ph"),
                    web_dir=str(tmp_path / "web"), admin_ids={999})


@pytest.fixture
def clock():
    return Clock(T0)


@pytest.fixture
def bot():
    return FakeBotApi()


@pytest.fixture
def app(settings, bot, clock):
    return create_app(settings, bot=bot, clock=clock)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app, settings):
    c = connect(settings.db_path)
    yield c
    c.close()


def auth(settings, user_id, clock=None):
    ts = int((clock.t if clock else datetime.now(timezone.utc)).timestamp())
    return {"Authorization": "tma " + make_init_data(user_id, settings.bot_token, ts)}


@pytest.fixture
def as_user(settings, clock):
    return lambda uid: auth(settings, uid, clock)


def make_place(db, name="Test Hotel", lat=12.2388, lon=109.1967, status="active",
               commercial=0, aliases=None, kind="hotel", district_id=None, **kw):
    import json
    from app.textgeo import fold
    cur = db.execute(
        "INSERT INTO places(name, name_fold, kind, lat, lon, district_id, commercial, aliases, "
        "status, created_at, price_from_vnd) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (name, fold(name), kind, lat, lon, district_id, commercial,
         json.dumps(aliases or [], ensure_ascii=False), status, T0.isoformat(),
         kw.get("price_from_vnd")))
    return cur.lastrowid


def make_user(db, uid):
    db.execute("INSERT OR IGNORE INTO users(id, created_at) VALUES(?,?)", (uid, T0.isoformat()))
    return uid


def make_review(db, place_id, user_id=1, text="Хорошее место", rating=5, tags=None,
                status="published", weight=1.0, photos=None, created_at=None, hold_reason=None):
    import json, hashlib
    make_user(db, user_id)
    cur = db.execute(
        "INSERT INTO reviews(place_id, user_id, status, rating, text, tags, lat, lon, photos, "
        "hold_reason, text_hash, weight, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (place_id, user_id, status, rating, text, json.dumps(tags or []), 12.2388, 109.1967,
         json.dumps(photos or []), hold_reason, hashlib.sha256(text.encode()).hexdigest(), weight,
         created_at or T0.isoformat()))
    return cur.lastrowid


def give_access(db, uid, days=3):
    from app.access import grant
    make_user(db, uid)
    grant(db, uid, days, "grant", None, T0)
