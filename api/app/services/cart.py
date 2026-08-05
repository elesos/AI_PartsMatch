from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from secrets import token_hex

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import CartItem, InquiryOrder, InquiryOrderItem, Machine, MachinePartRelation, Part, PartImage, PartQueryLog
from app.schemas.cart import CartAdd, InquirySubmit
from app.services.config_service import ConfigService


@dataclass(frozen=True)
class CartOwner:
    owner_key: str
    session_id: str | None = None
    user_id: str | None = None


class CartService:
    SAFETY_CATEGORIES = {"engine", "hydraulic", "electrical", "brake", "发动机", "液压", "电气", "制动"}

    def __init__(self, db: Session, owner: CartOwner) -> None:
        self.db, self.owner = db, owner

    def _part(self, part_id: str) -> Part:
        part = self.db.get(Part, part_id)
        if part is None or not part.is_active:
            raise AppError("active part not found", code=40420, status_code=404)
        return part

    def _requires_confirmation(self, part: Part, payload: CartAdd) -> bool:
        raw_threshold = ConfigService(self.db).get("cart.confirm_confidence_threshold", 0.70)
        try:
            threshold = min(1.0, max(0.0, float(raw_threshold)))
        except (TypeError, ValueError):
            threshold = 0.70
        configured = ConfigService(self.db).get("cart.safety_categories", sorted(self.SAFETY_CATEGORIES))
        categories = {str(value).strip().casefold() for value in configured} if isinstance(configured, list) else self.SAFETY_CATEGORIES
        category = (part.category or "").strip().casefold()
        return bool(payload.need_confirm or payload.match_status != "exact" or
                    (payload.confidence is not None and payload.confidence < threshold) or category in categories)

    def add(self, payload: CartAdd, *, query_id: str | None = None, commit: bool = True) -> CartItem:
        part = self._part(payload.part_id)
        need_confirm = self._requires_confirmation(part, payload)
        values = dict(
            owner_key=self.owner.owner_key, session_id=self.owner.session_id, user_id=self.owner.user_id,
            part_id=part.id, quantity=payload.quantity, match_status=payload.match_status,
            confidence=payload.confidence, source=payload.source, need_confirm=need_confirm, query_id=query_id,
        )
        dialect = self.db.get_bind().dialect.name
        insert = sqlite_insert(CartItem) if dialect == "sqlite" else pg_insert(CartItem)
        stmt = insert.values(**values).on_conflict_do_update(
            index_elements=[CartItem.owner_key, CartItem.part_id],
            set_={
                "quantity": CartItem.quantity + payload.quantity,
                "match_status": payload.match_status,
                "confidence": payload.confidence,
                "source": payload.source,
                "need_confirm": CartItem.need_confirm | need_confirm,
                "query_id": query_id,
                "updated_at": func.now(),
            },
        )
        self.db.execute(stmt)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.db.scalar(select(CartItem).where(
            CartItem.owner_key == self.owner.owner_key, CartItem.part_id == part.id
        ))

    def get(self, item_id: str) -> CartItem:
        item = self.db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.owner_key == self.owner.owner_key))
        if item is None:
            raise AppError("cart item not found", code=40421, status_code=404)
        return item

    def update(self, item_id: str, quantity: int) -> CartItem:
        item = self.get(item_id)
        self._part(item.part_id)
        item.quantity = quantity
        item.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: str) -> None:
        self.db.delete(self.get(item_id))
        self.db.commit()

    def _fitments(self, part_ids: list[str]) -> dict[str, list[dict]]:
        result = {part_id: [] for part_id in part_ids}
        rows = self.db.execute(select(MachinePartRelation, Machine).join(
            Machine, Machine.id == MachinePartRelation.machine_id
        ).where(MachinePartRelation.part_id.in_(part_ids), MachinePartRelation.is_active.is_(True)).order_by(Machine.brand, Machine.model)).all() if part_ids else []
        for relation, machine in rows:
            result[relation.part_id].append({
                "machine_id": machine.id, "brand": machine.brand, "model": machine.model,
                "machine_type": machine.machine_type, "engine_model": machine.engine_model,
                "system": relation.system, "position": relation.position,
            })
        return result

    def detailed_items(self) -> list[dict]:
        rows = self.db.execute(select(CartItem, Part).join(Part, Part.id == CartItem.part_id).where(
            CartItem.owner_key == self.owner.owner_key
        ).order_by(CartItem.created_at, CartItem.id)).all()
        part_ids = [part.id for _, part in rows]
        fitments = self._fitments(part_ids)
        images: dict[str, list[dict]] = {part_id: [] for part_id in part_ids}
        if part_ids:
            for image in self.db.scalars(select(PartImage).where(PartImage.part_id.in_(part_ids)).order_by(PartImage.sort_order, PartImage.id)):
                images[image.part_id].append({"id": image.id, "file_id": image.file_id, "url": image.url})
        result = []
        for item, part in rows:
            price = part.price or Decimal("0")
            result.append({
                "id": item.id, "part_id": part.id, "quantity": item.quantity,
                "match_status": item.match_status, "confidence": float(item.confidence) if item.confidence is not None else None,
                "source": item.source, "need_confirm": item.need_confirm, "query_id": item.query_id,
                "name": part.name_zh, "name_zh": part.name_zh, "name_en": part.name_en, "name_vi": part.name_vi,
                "part_no": part.part_no, "oem": part.oem_no, "oem_no": part.oem_no, "brand": part.brand,
                "category": part.category, "images": images[part.id], "image": images[part.id][0] if images[part.id] else None,
                "fitments": fitments[part.id], "unit_price": float(price), "subtotal": float(price * item.quantity),
                "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
            })
        return result

    def summary(self) -> dict:
        items = self.detailed_items()
        return {
            "total_items": len(items), "total_quantity": sum(item["quantity"] for item in items),
            "total_amount": round(sum(item["subtotal"] for item in items), 2),
            "need_confirm_count": sum(bool(item["need_confirm"]) for item in items), "items": items,
        }

    def validate_query(self, query_id: str | None) -> None:
        if query_id is None:
            return
        log = self.db.get(PartQueryLog, query_id)
        if log is None:
            raise AppError("query log not found", code=40422, status_code=404)
        if self.owner.session_id is not None and log.session_id != self.owner.session_id:
            raise AppError("query log does not belong to this session", code=40320, status_code=403)

    def submit(self, payload: InquirySubmit) -> InquiryOrder:
        summary = self.summary()
        if not summary["items"]:
            raise AppError("cart is empty", code=40920, status_code=409)
        order = InquiryOrder(
            order_no=f"INQ-{datetime.now(UTC):%Y%m%d%H%M%S}-{token_hex(3).upper()}",
            owner_key=self.owner.owner_key, session_id=self.owner.session_id, user_id=self.owner.user_id,
            contact_name=payload.contact_name, country=payload.country, contact_method=payload.contact_method,
            communication_tool=payload.communication_tool, note=payload.note, status="pending",
            total_quantity=summary["total_quantity"], total_amount=Decimal(str(summary["total_amount"])),
        )
        self.db.add(order)
        self.db.flush()
        for item in summary["items"]:
            self.db.add(InquiryOrderItem(
                order_id=order.id, part_id=item["part_id"], quantity=item["quantity"],
                unit_price=Decimal(str(item["unit_price"])), subtotal=Decimal(str(item["subtotal"])), snapshot=item,
            ))
        self.db.commit()
        self.db.refresh(order)
        return order
