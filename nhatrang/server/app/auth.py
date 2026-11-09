from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import Depends, HTTPException, Request

from .config import Settings
from .deps import get_conn, get_now, get_settings


class AuthError(Exception):
    pass


@dataclass
class TgUser:
    id: int
    first_name: str
    username: str | None


def verify_init_data(init_data: str, bot_token: str, now: int, max_age_s: int) -> TgUser:
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    got_hash = data.pop("hash", None)
    if not got_hash:
        raise AuthError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, got_hash):
        raise AuthError("bad hash")
    try:
        auth_date = int(data["auth_date"])
    except (KeyError, ValueError):
        raise AuthError("no auth_date")
    if now - auth_date > max_age_s or auth_date - now > 300:
        raise AuthError("expired")
    try:
        u = json.loads(data["user"])
        return TgUser(id=int(u["id"]), first_name=str(u.get("first_name", "")),
                      username=u.get("username"))
    except (KeyError, ValueError, TypeError):
        raise AuthError("no user")


def current_user(
    request: Request,
    conn=Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> TgUser:
    user: TgUser | None = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("tma "):
        try:
            user = verify_init_data(header[4:], settings.bot_token,
                                    int(now.timestamp()), settings.initdata_max_age_s)
        except AuthError:
            raise HTTPException(401, "bad initData")
    elif settings.dev_auth and request.headers.get("x-dev-user", "").isdigit():
        user = TgUser(id=int(request.headers["x-dev-user"]), first_name="Dev", username=None)
    if user is None:
        raise HTTPException(401, "auth required")
    conn.execute(
        "INSERT INTO users(id, first_name, username, created_at) VALUES(?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name, username=excluded.username",
        (user.id, user.first_name, user.username, now.isoformat()),
    )
    return user
