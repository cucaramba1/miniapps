from datetime import timedelta

from app.access import access_until
from tests.conftest import T0, make_user

SECRET = {"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"}


def upd(client, u):
    return client.post("/api/bot/webhook", json=u, headers=SECRET)


def pre(uid, payload, amount, cur="XTR"):
    return {"pre_checkout_query": {"id": "q1", "from": {"id": uid}, "currency": cur,
                                   "total_amount": amount, "invoice_payload": payload}}


def paid(uid, payload, amount, charge="ch1"):
    return {"message": {"from": {"id": uid}, "chat": {"id": uid},
                        "successful_payment": {"currency": "XTR", "total_amount": amount,
                                               "invoice_payload": payload,
                                               "telegram_payment_charge_id": charge}}}


def test_plans(client, as_user):
    r = client.get("/api/plans", headers=as_user(1)).json()
    assert {p["id"]: (p["days"], p["stars"]) for p in r} == {"d3": (3, 300), "d7": (7, 600)}


def test_invoice_created(client, bot, as_user):
    r = client.post("/api/pay/invoice", json={"plan": "d3"}, headers=as_user(5))
    assert r.status_code == 200 and r.json()["invoice_url"].startswith("https://")
    call = bot.named("create_invoice_link")[0]
    assert call["stars"] == 300 and call["payload"] == "d3:5"


def test_unknown_plan(client, as_user):
    assert client.post("/api/pay/invoice", json={"plan": "d30"}, headers=as_user(5)).status_code == 422


def test_pre_checkout(client, bot):
    upd(client, pre(5, "d3:5", 300))
    upd(client, pre(5, "d3:5", 299))
    upd(client, pre(6, "d3:5", 300))        # чужой payload
    upd(client, pre(5, "d3:5", 300, "USD"))
    upd(client, pre(5, "garbage", 300))
    assert [c["ok"] for c in bot.named("answer_pre_checkout")] == [True, False, False, False, False]


def test_successful_payment_idempotent(client, db, bot):
    make_user(db, 5)
    upd(client, paid(5, "d3:5", 300))
    upd(client, paid(5, "d3:5", 300))  # повторная доставка
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 1
    assert access_until(db, 5, T0) == T0 + timedelta(days=3)
    assert len(bot.named("send_message")) == 1


def test_payload_of_other_user_gives_nothing(client, db, bot):
    make_user(db, 5), make_user(db, 6)
    upd(client, paid(6, "d3:5", 300))
    assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0


def test_wrong_amount_gives_nothing(client, db):
    make_user(db, 5)
    upd(client, paid(5, "d3:5", 1))
    assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 0


def test_refund_revokes(client, db, bot):
    make_user(db, 5)
    upd(client, paid(5, "d7:5", 600, "chX"))
    assert access_until(db, 5, T0) is not None
    upd(client, {"message": {"from": {"id": 999}, "chat": {"id": 999}, "text": "/refund chX"}})
    assert bot.named("refund_star_payment") == [{"user_id": 5, "charge_id": "chX"}]
    assert access_until(db, 5, T0) is None
    # повторный возврат не дёргает Telegram
    upd(client, {"message": {"from": {"id": 999}, "chat": {"id": 999}, "text": "/refund chX"}})
    assert len(bot.named("refund_star_payment")) == 1


def test_paysupport_for_anyone(client, bot):
    upd(client, {"message": {"from": {"id": 12345}, "chat": {"id": 12345}, "text": "/paysupport"}})
    assert "возврат" in bot.named("send_message")[0]["text"].lower()
