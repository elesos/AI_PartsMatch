from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success
from app.models import LanguagePreference
from app.routers.cart import get_cart_owner
from app.schemas.i18n import LanguagePreferenceRequest
from app.services.cart import CartOwner
from app.services.config_service import ConfigService
from app.services.i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, messages, resolve_language

router = APIRouter(prefix="/api/v1/i18n", tags=["Internationalization"])


@router.get("/languages")
def languages(request: Request, db: Annotated[Session, Depends(get_db)]) -> dict:
    selected = resolve_language(request, db)
    return success({
        "current": selected,
        "languages": [{"code": code, "name": LANGUAGE_LABELS[code]} for code in SUPPORTED_LANGUAGES],
    })


@router.get("/messages")
def message_bundle(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    lang: Literal["zh", "en", "vi"] | None = Query(default=None),
) -> dict:
    selected = resolve_language(request, db, lang)
    return success({"lang": selected, "messages": messages(db, selected)})


@router.post("/preference")
def save_preference(
    payload: LanguagePreferenceRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[CartOwner, Depends(get_cart_owner)],
) -> dict:
    preference = db.scalar(select(LanguagePreference).where(LanguagePreference.owner_key == owner.owner_key))
    if preference is None:
        preference = LanguagePreference(owner_key=owner.owner_key, session_id=owner.session_id,
                                        user_id=owner.user_id, language=payload.lang)
        db.add(preference)
    else:
        preference.language = payload.lang
        preference.session_id, preference.user_id = owner.session_id, owner.user_id
    db.commit()
    config = ConfigService(db)
    cookie_name = str(config.get("i18n.cookie_name", "partsmatch_lang"))
    response.set_cookie(
        cookie_name, payload.lang, max_age=max(60, int(config.get("i18n.cookie_max_age", 31536000))),
        httponly=True, samesite="lax", secure=bool(config.get("i18n.cookie_secure", True)), path="/",
    )
    return success({"lang": payload.lang, "source": "manual", "owner": owner.owner_key.split(":", 1)[0]})
