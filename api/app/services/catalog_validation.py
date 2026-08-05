"""Cross-cutting catalogue invariants that cannot be expressed as SQL constraints."""
import re

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import CartItem, Part


def normalize_part_number(value: str) -> str:
    """Canonical representation used by writes, lookups, and cache keys."""
    return re.sub(r"\s+", "", value).upper()


@event.listens_for(Session, "before_flush")
def prevent_inactive_cart_items(session: Session, _flush_context, _instances) -> None:
    for item in session.new.union(session.dirty):
        if isinstance(item, Part):
            item.part_no = normalize_part_number(item.part_no)
            item.oem_no = normalize_part_number(item.oem_no) if item.oem_no else None
    for item in session.new:
        if not isinstance(item, CartItem):
            continue
        is_active = session.scalar(select(Part.is_active).where(Part.id == item.part_id))
        if is_active is False:
            raise AppError(
                "inactive parts cannot be added to a cart", code=42250, status_code=422,
                data={"field": "part_id", "reason": "inactive"},
            )


def active_parts_statement():
    """Canonical base statement for customer-facing search and listing."""
    return select(Part).where(Part.is_active.is_(True))
