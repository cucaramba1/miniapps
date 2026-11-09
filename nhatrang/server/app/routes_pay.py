from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .auth import TgUser, current_user
from .config import Settings
from .deps import get_settings
from .payments import get_plans, make_payload

router = APIRouter(prefix="/api")


class InvoiceReq(BaseModel):
    plan: str


@router.get("/plans")
def plans(s: Settings = Depends(get_settings)):
    return [{"id": k, "days": p.days, "stars": p.stars, "rub": p.rub}
            for k, p in get_plans(s).items()]


@router.post("/pay/invoice")
def invoice(req: InvoiceReq, request: Request, user: TgUser = Depends(current_user),
            s: Settings = Depends(get_settings)):
    plan = get_plans(s).get(req.plan)
    if plan is None:
        raise HTTPException(422, "unknown plan")
    bot = request.app.state.bot
    if bot is None:
        raise HTTPException(503, "bot not configured")
    url = bot.create_invoice_link(f"Доступ на {plan.days} дн.", "Отзывы, фото и контакты в приложении",
                                  make_payload(req.plan, user.id), plan.stars)
    return {"invoice_url": url}
