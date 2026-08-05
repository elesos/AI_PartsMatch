from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.core.security import ALGORITHM
from app.models import AdminUser
from app.schemas.cart import CartAdd, CartFromMatch, CartUpdate, InquirySubmit
from app.services.cart import CartOwner, CartService

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$")


def get_cart_owner(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
) -> CartOwner:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            payload = jwt.decode(authorization[7:].strip(), get_settings().jwt_secret, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
        except JWTError as error:
            raise AppError("invalid or expired token", code=40120, status_code=401) from error
        user = db.get(AdminUser, user_id) if user_id else None
        if user is None or not user.is_active:
            raise AppError("invalid user", code=40121, status_code=401)
        return CartOwner(owner_key=f"user:{user.id}", user_id=user.id)
    if x_session_id is None:
        raise AppError("X-Session-Id header is required for anonymous cart", code=40020, status_code=400)
    if not SESSION_PATTERN.fullmatch(x_session_id):
        raise AppError("invalid X-Session-Id", code=40021, status_code=400)
    return CartOwner(owner_key=f"session:{x_session_id}", session_id=x_session_id)


def _service(db: Session, owner: CartOwner) -> CartService:
    return CartService(db, owner)


@router.get("")
def get_cart(db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    return success({"items": _service(db, owner).detailed_items()})


@router.post("/items", status_code=201)
def add_item(payload: CartAdd, db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    item = _service(db, owner).add(payload)
    return success({"id": item.id, "part_id": item.part_id, "quantity": item.quantity,
                    "need_confirm": item.need_confirm, "source": item.source, "match_status": item.match_status})


@router.put("/items/{item_id}")
def update_item(item_id: str, payload: CartUpdate, db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    item = _service(db, owner).update(item_id, payload.quantity)
    return success({"id": item.id, "part_id": item.part_id, "quantity": item.quantity,
                    "need_confirm": item.need_confirm, "source": item.source, "match_status": item.match_status})


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> Response:
    _service(db, owner).delete(item_id)
    return Response(status_code=204)


@router.get("/summary")
def cart_summary(db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    return success(_service(db, owner).summary())


@router.post("/submit", status_code=201)
def submit_cart(payload: InquirySubmit, db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    order = _service(db, owner).submit(payload)
    return success({"order_id": order.id, "order_no": order.order_no, "status": order.status,
                    "total_quantity": order.total_quantity, "total_amount": float(order.total_amount)})


@router.post("/items/from-match", status_code=201)
def add_from_match(payload: CartFromMatch, db: Annotated[Session, Depends(get_db)], owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = _service(db, owner)
    service.validate_query(payload.query_id)
    item = service.add(CartAdd(
        part_id=payload.part_id, quantity=payload.quantity, match_status=payload.match_status,
        confidence=payload.confidence, source=payload.source,
    ), query_id=payload.query_id)
    return success({"id": item.id, "part_id": item.part_id, "quantity": item.quantity,
                    "need_confirm": item.need_confirm, "source": item.source,
                    "match_status": item.match_status, "query_id": item.query_id})
