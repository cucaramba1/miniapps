"""Тестовый сервер для UI-тестов: свежая БД во временной папке, сид-данные, ПОДДЕЛЬНЫЙ бот.
  python -m tools.test_server <port> <db_dir>
Тестовые токены известны (BOT_TOKEN=test-token), в боевой конфиг это попасть не должно."""
from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

from app.config import Settings
from app.db import connect, migrate
from app.main import create_app
from tools.seed_test import seed


class TestBot:
    def __init__(self):
        self.calls = []

    def send_message(self, chat_id, text, reply_markup=None): self.calls.append(("send_message", chat_id, text))
    def answer_callback(self, callback_id, text): pass
    def create_invoice_link(self, title, description, payload, stars): return f"https://t.me/$test_{payload}_{stars}"
    def answer_pre_checkout(self, query_id, ok, error=None): pass
    def refund_star_payment(self, user_id, charge_id): pass


if __name__ == "__main__":
    port, d = int(sys.argv[1]), Path(sys.argv[2])
    d.mkdir(parents=True, exist_ok=True)
    s = Settings(db_path=str(d / "t.db"), photos_dir=str(d / "ph"), dev_auth=True, admin_ids={999})
    c = connect(s.db_path)
    migrate(c)
    seed(c)
    c.close()
    uvicorn.run(create_app(s, bot=TestBot()), host="127.0.0.1", port=port, log_level="warning")
