from __future__ import annotations

import logging
from dataclasses import dataclass

from .access import grant, revoke_by_ref
from .bot import Ctx
from .config import Settings

log = logging.getLogger("payments")


@dataclass
class Plan:
    days: int
    stars: int
    rub: int


def get_plans(s: Settings) -> dict[str, Plan]:
    return {"d3": Plan(3, s.plan_d3_stars, s.plan_d3_rub),
            "d7": Plan(7, s.plan_d7_stars, s.plan_d7_rub)}


def make_payload(plan: str, user_id: int) -> str:
    return f"{plan}:{user_id}"


def _parse_payload(payload: str, settings: Settings):
    try:
        plan_id, uid = payload.split(":")
        plan = get_plans(settings)[plan_id]
        return plan_id, plan, int(uid)
    except (ValueError, KeyError):
        return None


def _valid(settings: Settings, payer_id: int, payload: str, currency: str, amount: int):
    parsed = _parse_payload(payload, settings)
    if not parsed:
        return None
    plan_id, plan, uid = parsed
    if uid != payer_id or currency != "XTR" or amount != plan.stars:
        return None
    return plan_id, plan


def on_pre_checkout(ctx: Ctx, q: dict) -> None:
    ok = _valid(ctx.settings, q["from"]["id"], q.get("invoice_payload", ""),
                q.get("currency", ""), q.get("total_amount", -1))
    if ok:
        ctx.bot.answer_pre_checkout(q["id"], True)
    else:
        ctx.bot.answer_pre_checkout(q["id"], False, "Не удалось проверить заказ. Попробуйте ещё раз.")


def on_successful_payment(ctx: Ctx, msg: dict) -> None:
    sp = msg["successful_payment"]
    uid = msg["from"]["id"]
    ok = _valid(ctx.settings, uid, sp.get("invoice_payload", ""),
                sp.get("currency", ""), sp.get("total_amount", -1))
    if not ok:
        log.error("payment mismatch: %s", sp)
        for a in ctx.settings.admin_ids:
            ctx.bot.send_message(a, f"Платёж не сошёлся, доступ НЕ выдан: user {uid}, {sp}")
        return
    plan_id, plan = ok
    charge = sp["telegram_payment_charge_id"]
    ctx.conn.execute("BEGIN IMMEDIATE")
    try:
        cur = ctx.conn.execute(
            "INSERT OR IGNORE INTO payments(user_id, plan, stars, charge_id, created_at) "
            "VALUES(?,?,?,?,?)", (uid, plan_id, plan.stars, charge, ctx.now.isoformat()))
        fresh = cur.rowcount == 1
        if fresh:
            grant(ctx.conn, uid, plan.days, "stars", charge, ctx.now)
        ctx.conn.execute("COMMIT")
    except BaseException:
        if ctx.conn.in_transaction:
            ctx.conn.execute("ROLLBACK")
        raise
    if fresh:
        ctx.bot.send_message(msg["chat"]["id"], f"Оплата прошла. Доступ открыт на {plan.days} дн.")


def refund(ctx: Ctx, chat_id: int, charge_id: str) -> None:
    p = ctx.conn.execute("SELECT user_id, refunded_at FROM payments WHERE charge_id=?",
                         (charge_id,)).fetchone()
    if p is None:
        ctx.bot.send_message(chat_id, "Платёж не найден.")
        return
    if p["refunded_at"]:
        ctx.bot.send_message(chat_id, "Этот платёж уже возвращён.")
        return
    try:
        ctx.bot.refund_star_payment(p["user_id"], charge_id)
    except Exception as e:  # возврат не прошёл: в БД ничего не меняем
        ctx.bot.send_message(chat_id, f"Telegram отклонил возврат: {e}")
        return
    ctx.conn.execute("UPDATE payments SET refunded_at=? WHERE charge_id=?",
                     (ctx.now.isoformat(), charge_id))
    revoke_by_ref(ctx.conn, charge_id, ctx.now)
    ctx.bot.send_message(chat_id, "Возврат выполнен, доступ отозван.")
