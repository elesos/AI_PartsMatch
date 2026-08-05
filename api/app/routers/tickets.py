from datetime import datetime
from typing import Annotated, Literal

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.core.security import require_role
from app.models import AdminUser
from app.routers.cart import get_cart_owner
from app.schemas.tickets import (TicketAdminNote, TicketAssign, TicketCreate, TicketResolve, TicketStatus,
                                 TicketStatusUpdate, TicketSupplement)
from app.services.cart import CartOwner
from app.services.tickets import TicketService

router = APIRouter(prefix="/api/v1/tickets", tags=["Manual tickets"])
admin_router = APIRouter(prefix="/api/v1/admin/tickets", tags=["Admin manual tickets"])


@router.post("", status_code=201)
def create_ticket(payload: TicketCreate, db: Annotated[Session, Depends(get_db)],
                  owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = TicketService(db)
    return success(service.serialize(service.create(payload, owner)))


@router.get("/status")
def get_ticket_status(
    ticket_no: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
    owner: Annotated[CartOwner, Depends(get_cart_owner)],
) -> dict:
    # Reject malformed references before querying so this endpoint cannot be used
    # as a loose ticket-number oracle. Missing, malformed and foreign tickets share
    # exactly the same public response.
    if not re.fullmatch(r"MT-\d{8}-[0-9A-F]{32}", ticket_no):
        raise AppError("ticket not found", code=40431, status_code=404)
    service = TicketService(db)
    return success(service.serialize_status(service.owned_by_number(ticket_no, owner)))


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, db: Annotated[Session, Depends(get_db)],
               owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = TicketService(db)
    return success(service.serialize(service.owned(ticket_id, owner)))


@router.post("/{ticket_id}/supplement")
def supplement(ticket_id: str, payload: TicketSupplement, db: Annotated[Session, Depends(get_db)],
               owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = TicketService(db); ticket = service.owned(ticket_id, owner)
    service.supplement(ticket, payload.content)
    return success(service.serialize(ticket))


@router.post("/{ticket_id}/add-to-cart")
def add_to_cart(ticket_id: str, db: Annotated[Session, Depends(get_db)],
                owner: Annotated[CartOwner, Depends(get_cart_owner)]) -> dict:
    service = TicketService(db); ticket = service.owned(ticket_id, owner)
    parts = service.add_to_cart(ticket, owner)
    return success({"ticket_id": ticket.id, "status": ticket.status, "added": [
        {"part_id": item.part_id, "quantity": item.quantity} for item in parts]})


@admin_router.get("")
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role("operator", "admin"))],
    status: TicketStatus | None = None, assignee_id: str | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None,
    machine_brand: str | None = None, page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["priority", "created_at", "updated_at"] = "priority",
    order: Literal["asc", "desc"] = "asc",
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise AppError("date_from must not be after date_to", code=40030, status_code=400)
    return success(TicketService(db).list_admin(status=status, assignee_id=assignee_id, date_from=date_from,
        date_to=date_to, machine_brand=machine_brand, page=page, page_size=page_size, sort=sort, order=order))


@admin_router.get("/stats")
def ticket_stats(db: Annotated[Session, Depends(get_db)],
                 _: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    return success(TicketService(db).stats())


@admin_router.get("/options")
def ticket_options(db: Annotated[Session, Depends(get_db)],
                   _: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    return success(TicketService(db).options())


@admin_router.get("/{ticket_id}")
def admin_get_ticket(ticket_id: str, db: Annotated[Session, Depends(get_db)],
                     _: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    service = TicketService(db)
    return success(service.serialize(service.get(ticket_id), admin=True))


@admin_router.put("/{ticket_id}/status")
def update_status(ticket_id: str, payload: TicketStatusUpdate, db: Annotated[Session, Depends(get_db)],
                  actor: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    service = TicketService(db); ticket = service.get(ticket_id)
    if payload.status in {"matched", "in_cart"}:
        raise AppError("use resolve or add-to-cart for this transition", code=40935, status_code=409)
    service.transition(ticket, payload.status, actor_id=actor.id, note=payload.note)
    return success(service.serialize(ticket, admin=True))


@admin_router.post("/{ticket_id}/assign")
def assign(ticket_id: str, payload: TicketAssign, db: Annotated[Session, Depends(get_db)],
           actor: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    service = TicketService(db); ticket = service.get(ticket_id)
    service.assign(ticket, payload.assignee_id, actor_id=actor.id)
    return success(service.serialize(ticket, admin=True))


@admin_router.post("/{ticket_id}/resolve")
def resolve(ticket_id: str, payload: TicketResolve, db: Annotated[Session, Depends(get_db)],
            actor: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    service = TicketService(db); ticket = service.get(ticket_id)
    service.resolve(ticket, payload, actor_id=actor.id)
    return success(service.serialize(ticket, admin=True))


@admin_router.post("/{ticket_id}/notes")
def add_note(ticket_id: str, payload: TicketAdminNote, db: Annotated[Session, Depends(get_db)],
             actor: Annotated[AdminUser, Depends(require_role("operator", "admin"))]) -> dict:
    service = TicketService(db); ticket = service.get(ticket_id)
    service.add_note(ticket, payload.content, actor_id=actor.id)
    return success(service.serialize(ticket, admin=True))
