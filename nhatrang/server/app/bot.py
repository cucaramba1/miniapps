from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from .access import access_until, grant, revoke_by_ref
from .config import Settings
from .reviews import publish_review, reject_review, revoke_review

log = logging.getLogger("bot")


class BotApi(Protocol):
    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None: ...
    def answer_callback(self, callback_id: str, text: str) -> None: ...
    def create_invoice_link(self, title: str, description: str, payload: str, stars: int) -> str: ...
    def answer_pre_checkout(self, query_id: str, ok: bool, error: str | None = None) -> None: ...
    def refund_star_payment(self, user_id: int, charge_id: str) -> None: ...


class HttpBotApi:
    def __init__(self, token: str):
        self._base = f"https://api.telegram.org/bot{token}/"
        self._http = httpx.Client(timeout=15)

    def _call(self, method: str, **params):
        r = self._http.post(self._base + method, json=params)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method}: {data.get('description')}")
        return data["result"]

    def send_message(self, chat_id, text, reply_markup=None):
        p = {"chat_id": chat_id, "text": text}
        if reply_markup:
            p["reply_markup"] = reply_markup
        self._call("sendMessage", **p)

    def answer_callback(self, callback_id, text):
        self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def create_invoice_link(self, title, description, payload, stars):
        return self._call("createInvoiceLink", title=title, description=description,
                          payload=payload, currency="XTR",
                          prices=[{"label": title, "amount": stars}])

    def answer_pre_checkout(self, query_id, ok, error=None):
        p = {"pre_checkout_query_id": query_id, "ok": ok}
        if error:
            p["error_message"] = error
        self._call("answerPreCheckoutQuery", **p)

    def refund_star_payment(self, user_id, charge_id):
        self._call("refundStarPayment", user_id=user_id, telegram_payment_charge_id=charge_id)


@dataclass
class Ctx:
    conn: sqlite3.Connection
    settings: Settings
    bot: BotApi
    now: datetime


# ---------- модерация ----------

def approve_place(ctx: Ctx, place_id: int) -> str:
    p = ctx.conn.execute("SELECT status FROM places WHERE id=?", (place_id,)).fetchone()
    if p is None or p["status"] != "pending":
        return "уже обработано"
    ctx.conn.execute("UPDATE places SET status='active' WHERE id=?", (place_id,))
    from .districts import assign_districts
    assign_districts(ctx.conn)
    ids = [r[0] for r in ctx.conn.execute(
        "SELECT id FROM reviews WHERE place_id=? AND status='held' AND hold_reason='place_pending'",
        (place_id,))]
    for rid in ids:
        publish_review(ctx.conn, rid, ctx.settings, ctx.now)
    return f"место одобрено, отзывов опубликовано: {len(ids)}"


def reject_place(ctx: Ctx, place_id: int) -> str:
    p = ctx.conn.execute("SELECT status FROM places WHERE id=?", (place_id,)).fetchone()
    if p is None or p["status"] != "pending":
        return "уже обработано"
    ctx.conn.execute("UPDATE places SET status='rejected' WHERE id=?", (place_id,))
    ids = [r[0] for r in ctx.conn.execute(
        "SELECT id FROM reviews WHERE place_id=? AND status='held'", (place_id,))]
    for rid in ids:
        reject_review(ctx.conn, rid, ctx.now)
    return "место отклонено"


def _next_queue_item(conn):
    p = conn.execute("SELECT * FROM places WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
    if p:
        return "place", p
    r = conn.execute(
        "SELECT * FROM reviews WHERE status='held' AND hold_reason IS NOT 'place_pending' "
        "ORDER BY id LIMIT 1").fetchone()
    return ("review", r) if r else (None, None)


def _cmd_queue(ctx: Ctx, chat_id: int):
    kind, row = _next_queue_item(ctx.conn)
    if kind is None:
        ctx.bot.send_message(chat_id, "Очередь пуста.")
        return
    kb = lambda k, i: {"inline_keyboard": [[{"text": "Одобрить", "callback_data": f"ok:{k}:{i}"},
                                            {"text": "Отклонить", "callback_data": f"no:{k}:{i}"}]]}
    if kind == "place":
        txt = (f"Новое место #{row['id']}\n{row['name']} ({row['kind']})\n"
               f"https://www.openstreetmap.org/?mlat={row['lat']}&mlon={row['lon']}#map=19/{row['lat']}/{row['lon']}")
    else:
        txt = (f"Отзыв #{row['id']} (место {row['place_id']}), причина: {row['hold_reason']}\n"
               f"Оценка {row['rating']}, автор {row['user_id']}\n\n{row['text'][:900]}")
    ctx.bot.send_message(chat_id, txt, kb(kind, row["id"]))


def _on_callback(ctx: Ctx, cq: dict):
    if cq["from"]["id"] not in ctx.settings.admin_ids:
        return
    try:
        verb, kind, sid = cq["data"].split(":")
        i = int(sid)
    except ValueError:
        return
    if kind == "place":
        msg = approve_place(ctx, i) if verb == "ok" else reject_place(ctx, i)
    elif kind == "review":
        ok = publish_review(ctx.conn, i, ctx.settings, ctx.now) if verb == "ok" \
            else reject_review(ctx.conn, i, ctx.now)
        msg = "готово" if ok else "уже обработано"
    else:
        return
    ctx.bot.answer_callback(cq["id"], msg)


def _cmd_stats(ctx: Ctx, chat_id: int):
    def q(sql: str) -> int:
        return ctx.conn.execute(sql).fetchone()[0]

    def n(table: str, status: str) -> int:
        return q(f"SELECT COUNT(*) FROM {table} WHERE status='{status}'")

    paid = "FROM payments WHERE refunded_at IS NULL"
    ctx.bot.send_message(chat_id, (
        f"Пользователей: {q('SELECT COUNT(*) FROM users')}\n"
        f"Мест активных: {n('places', 'active')}, на проверке: {n('places', 'pending')}\n"
        f"Отзывов опубликовано: {n('reviews', 'published')}, удержано: {n('reviews', 'held')}\n"
        f"Платежей: {q('SELECT COUNT(*) ' + paid)}, "
        f"Stars: {q('SELECT COALESCE(SUM(stars),0) ' + paid)}"))


def _cmd_start(ctx: Ctx, chat_id: int):
    kb = None
    if ctx.settings.webapp_url:
        kb = {"inline_keyboard": [[{"text": "Открыть",
                                    "web_app": {"url": ctx.settings.webapp_url}}]]}
    ctx.bot.send_message(chat_id, "Нячанг Дом: правда о жилье до заезда.", kb)


def handle_update(update: dict, ctx: Ctx) -> None:
    from . import payments  # поздний импорт: payments использует Ctx отсюда
    if "pre_checkout_query" in update:
        payments.on_pre_checkout(ctx, update["pre_checkout_query"])
        return
    if "callback_query" in update:
        _on_callback(ctx, update["callback_query"])
        return
    msg = update.get("message")
    if not msg:
        return
    if "successful_payment" in msg:
        payments.on_successful_payment(ctx, msg)
        return
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return
    uid, chat = msg["from"]["id"], msg["chat"]["id"]
    parts = text.split()
    cmd, args = parts[0].split("@")[0], parts[1:]
    if cmd == "/start":
        _cmd_start(ctx, chat)
    elif cmd == "/paysupport":
        ctx.bot.send_message(chat, ctx.settings.support_text)
    elif uid not in ctx.settings.admin_ids:
        return  # админ-команды: чужим молчание
    elif cmd == "/queue":
        _cmd_queue(ctx, chat)
    elif cmd == "/stats":
        _cmd_stats(ctx, chat)
    elif cmd == "/revoke" and len(args) == 1 and args[0].isdigit():
        ok = revoke_review(ctx.conn, int(args[0]), ctx.now)
        ctx.bot.send_message(chat, "Отозван." if ok else "Не найден или уже отозван.")
    elif cmd == "/grant" and len(args) == 2 and all(a.isdigit() for a in args):
        uid2, days = int(args[0]), int(args[1])
        if not ctx.conn.execute("SELECT 1 FROM users WHERE id=?", (uid2,)).fetchone():
            ctx.bot.send_message(chat, "Такого пользователя нет (он должен хотя бы раз открыть приложение).")
        elif 0 < days <= 365:
            grant(ctx.conn, uid2, days, "grant", None, ctx.now)
            until = access_until(ctx.conn, uid2, ctx.now)
            ctx.bot.send_message(chat, f"Выдано {days} дн. Доступ до {until:%Y-%m-%d %H:%M} UTC.")
    elif cmd == "/refund" and len(args) == 1:
        payments.refund(ctx, chat, args[0])
