from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_hex

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import (AdminUser, ExcelBatch, FileObject, KnowledgeCandidate, ManualTicket, ManualTicketAttachment,
                        ManualTicketCartAddition, ManualTicketEvent, ManualTicketPart, ManualTicketSupplement, Part,
                        PartQueryLog)
from app.schemas.cart import CartAdd
from app.schemas.tickets import TicketCreate, TicketResolve
from app.services.cart import CartOwner, CartService
from app.services.config_service import ConfigService


class TicketService:
    TRANSITIONS = {
        "pending": {"processing"}, "processing": {"need_info", "matched"},
        "need_info": {"processing"}, "matched": {"in_cart", "closed"},
        "in_cart": {"closed"}, "closed": set(),
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _ticket_no() -> str:
        return f"MT-{datetime.now(UTC):%Y%m%d}-{token_hex(16).upper()}"

    def create(self, payload: TicketCreate, owner: CartOwner, *, commit: bool = True) -> ManualTicket:
        if payload.image_ids:
            files = self.db.scalars(select(FileObject).where(FileObject.id.in_(payload.image_ids))).all()
            by_id = {item.id: item for item in files}
            if len(by_id) != len(set(payload.image_ids)) or any(
                by_id[file_id].owner_key != owner.owner_key for file_id in payload.image_ids
            ):
                raise AppError("image attachment not found for this session", code=40430, status_code=404)
        # Excel batches are owned by api/03. Until that table lands the opaque optional id is retained;
        # api/03 must validate owner_key and add its FK before accepting processing.
        ticket = ManualTicket(
            ticket_no=self._ticket_no(), owner_key=owner.owner_key, session_id=owner.session_id, user_id=owner.user_id,
            status="pending", contact_name=payload.contact_name, contact_value=payload.contact_info,
            country=payload.country or None, communication_tool=payload.communication_tool,
            machine_type=payload.machine_type or None, machine_brand=payload.machine_brand or None,
            machine_model=payload.machine_model or None, serial_no=payload.serial_no or None,
            engine_model=payload.engine_model or None, query_text=payload.part_description,
            quantity=payload.quantity, note=payload.note or None, ai_preliminary_result=payload.ai_preliminary_result,
            extracted_info={}, excel_batch_id=payload.excel_batch_id,
        )
        self.db.add(ticket)
        self.db.flush()
        self.db.add(PartQueryLog(
            session_id=owner.session_id, user_id=owner.user_id, query_type="manual", source_id=ticket.id,
            query_text=payload.part_description,
            request_data={"ticket_id": ticket.id, "image_ids": list(dict.fromkeys(payload.image_ids)),
                          "excel_batch_id": payload.excel_batch_id},
            raw_input={"description": payload.part_description, "quantity": payload.quantity},
            extracted_info={"machine_type": payload.machine_type or None, "machine_brand": payload.machine_brand or None,
                            "machine_model": payload.machine_model or None, "serial_no": payload.serial_no or None,
                            "engine_model": payload.engine_model or None},
            ai_result=payload.ai_preliminary_result or None, result_count=0, match_status="insufficient",
            need_manual=True,
        ))
        self._event(ticket, "created", status_to="pending")
        for file_id in dict.fromkeys(payload.image_ids):
            self.db.add(ManualTicketAttachment(ticket_id=ticket.id, file_id=file_id))
        if commit:
            self.db.commit(); self.db.refresh(ticket)
        return ticket

    def owned(self, ticket_id: str, owner: CartOwner) -> ManualTicket:
        ticket = self.db.scalar(select(ManualTicket).where(ManualTicket.id == ticket_id,
                                                           ManualTicket.owner_key == owner.owner_key))
        if ticket is None:
            raise AppError("ticket not found", code=40431, status_code=404)
        return ticket

    def owned_by_number(self, ticket_no: str, owner: CartOwner) -> ManualTicket:
        ticket = self.db.scalar(select(ManualTicket).where(
            ManualTicket.ticket_no == ticket_no, ManualTicket.owner_key == owner.owner_key))
        if ticket is None:
            raise AppError("ticket not found", code=40431, status_code=404)
        return ticket

    def get(self, ticket_id: str) -> ManualTicket:
        ticket = self.db.get(ManualTicket, ticket_id)
        if ticket is None:
            raise AppError("ticket not found", code=40431, status_code=404)
        return ticket

    def _event(self, ticket: ManualTicket, event_type: str, *, actor_id: str | None = None,
               status_from: str | None = None, status_to: str | None = None, content: str | None = None) -> None:
        self.db.add(ManualTicketEvent(ticket_id=ticket.id, actor_id=actor_id, event_type=event_type,
                                      status_from=status_from, status_to=status_to, content=content or None,
                                      created_at=datetime.now(UTC)))

    def transition(self, ticket: ManualTicket, target: str, *, actor_id: str | None = None, note: str = "") -> None:
        if target not in self.TRANSITIONS.get(ticket.status, set()):
            raise AppError(f"invalid ticket transition: {ticket.status} -> {target}", code=40930, status_code=409)
        previous = ticket.status
        ticket.status = target
        self._event(ticket, "status_changed", actor_id=actor_id, status_from=previous, status_to=target, content=note)
        self.db.commit(); self.db.refresh(ticket)

    def supplement(self, ticket: ManualTicket, content: str) -> None:
        if ticket.status != "need_info":
            raise AppError("supplement is only allowed when information is requested", code=40931, status_code=409)
        self.db.add(ManualTicketSupplement(ticket_id=ticket.id, content=content))
        self._event(ticket, "supplemented", status_from="need_info", status_to="processing", content=content)
        ticket.status = "processing"
        self.db.commit()

    def assign(self, ticket: ManualTicket, assignee_id: str, *, actor_id: str | None = None) -> None:
        assignee = self.db.get(AdminUser, assignee_id)
        if assignee is None or not assignee.is_active or assignee.role not in {"operator", "admin"}:
            raise AppError("active operator not found", code=40432, status_code=404)
        previous_status = ticket.status
        ticket.assignee_id = assignee.id
        if ticket.status == "pending":
            ticket.status = "processing"
        self._event(ticket, "assigned", actor_id=actor_id, status_from=previous_status, status_to=ticket.status,
                    content=assignee.username)
        self.db.commit(); self.db.refresh(ticket)

    def _candidate_payload(self, ticket: ManualTicket, payload: TicketResolve) -> dict:
        return {"source": {"type": "manual_ticket", "ticket_id": ticket.id, "ticket_no": ticket.ticket_no},
                "part_ids": payload.resolved_part_ids,
                "quantities": {part_id: payload.quantities.get(part_id, ticket.quantity) for part_id in payload.resolved_part_ids},
                "confidences": {part_id: payload.confidences.get(part_id) for part_id in payload.resolved_part_ids},
                "reasons": {part_id: payload.reasons.get(part_id, "") for part_id in payload.resolved_part_ids},
                "machine": {"type": ticket.machine_type, "brand": ticket.machine_brand, "model": ticket.machine_model,
                            "serial_no": ticket.serial_no, "engine_model": ticket.engine_model},
                "evidence": payload.match_evidence, "internal_note": payload.internal_note}

    def resolve(self, ticket: ManualTicket, payload: TicketResolve, *, actor_id: str | None = None) -> None:
        ticket = self.db.scalar(select(ManualTicket).where(ManualTicket.id == ticket.id).with_for_update())
        candidate_payload = self._candidate_payload(ticket, payload)
        candidate = self.db.scalar(select(KnowledgeCandidate).where(KnowledgeCandidate.ticket_id == ticket.id))
        if ticket.status == "matched":
            if candidate is not None and candidate.payload == candidate_payload:
                return
            raise AppError("ticket was already resolved with different content", code=40936, status_code=409)
        if ticket.status not in {"processing", "need_info"}:
            raise AppError("ticket cannot be resolved in its current status", code=40932, status_code=409)
        parts = self.db.scalars(select(Part).where(Part.id.in_(payload.resolved_part_ids), Part.is_active.is_(True))).all()
        if {part.id for part in parts} != set(payload.resolved_part_ids):
            raise AppError("all resolved parts must exist and be active", code=40433, status_code=404)
        self.db.execute(delete(ManualTicketPart).where(ManualTicketPart.ticket_id == ticket.id))
        for part_id in payload.resolved_part_ids:
            self.db.add(ManualTicketPart(ticket_id=ticket.id, part_id=part_id,
                                          quantity=payload.quantities.get(part_id, ticket.quantity),
                                          confidence=payload.confidences.get(part_id), reason=payload.reasons.get(part_id) or None))
        ticket.result_part_id = payload.resolved_part_ids[0]
        ticket.match_evidence = payload.match_evidence
        ticket.internal_note = payload.internal_note or None
        ticket.status = "matched"
        if candidate is None:
            self.db.add(KnowledgeCandidate(ticket_id=ticket.id, payload=candidate_payload, status="pending_review"))
        else:
            candidate.payload, candidate.status = candidate_payload, "pending_review"
        self._event(ticket, "resolved", actor_id=actor_id, status_from="processing", status_to="matched",
                    content=payload.match_evidence)
        self.db.commit(); self.db.refresh(ticket)

    def add_note(self, ticket: ManualTicket, content: str, *, actor_id: str) -> None:
        self._event(ticket, "internal_note", actor_id=actor_id, content=content)
        self.db.commit()

    def add_to_cart(self, ticket: ManualTicket, owner: CartOwner) -> list[ManualTicketPart]:
        # Serialize additions for this ticket. The unique marker is created in the same
        # transaction as all cart upserts, so retries and concurrent requests are safe.
        ticket = self.db.scalar(select(ManualTicket).where(
            ManualTicket.id == ticket.id, ManualTicket.owner_key == owner.owner_key).with_for_update())
        if ticket.status not in {"matched", "in_cart"}:
            raise AppError("only matched tickets can be added to cart", code=40933, status_code=409)
        existing = self.db.scalar(select(ManualTicketCartAddition).where(
            ManualTicketCartAddition.ticket_id == ticket.id, ManualTicketCartAddition.owner_key == owner.owner_key))
        parts = self.db.scalars(select(ManualTicketPart).where(ManualTicketPart.ticket_id == ticket.id)).all()
        if not parts:
            raise AppError("ticket has no resolved parts", code=40934, status_code=409)
        if existing is None:
            self.db.add(ManualTicketCartAddition(ticket_id=ticket.id, owner_key=owner.owner_key))
            self.db.flush()
            cart = CartService(self.db, owner)
            for item in parts:
                cart.add(CartAdd(part_id=item.part_id, quantity=item.quantity, match_status="exact", source="manual"),
                         commit=False)
            ticket.status = "in_cart"
            self.db.commit()
        return parts

    def mask_contact(self, value: str) -> str:
        config = ConfigService(self.db)
        try:
            prefix = max(0, min(20, int(config.get("ticket.contact_mask_prefix", 3))))
            suffix = max(0, min(20, int(config.get("ticket.contact_mask_suffix", 4))))
        except (TypeError, ValueError):
            prefix, suffix = 3, 4
        if "@" in value:
            local, domain = value.split("@", 1)
            return (local[:1] + "****" if local else "****") + "@" + domain
        if len(value) <= prefix + suffix:
            return "*" * len(value)
        return value[:prefix] + "****" + value[-suffix:]

    def attachments(self, ticket_id: str) -> list[dict]:
        rows = self.db.execute(select(FileObject).join(ManualTicketAttachment,
            ManualTicketAttachment.file_id == FileObject.id).where(ManualTicketAttachment.ticket_id == ticket_id)).scalars()
        return [{"image_id": item.id, "url": item.url, "original_name": item.original_name,
                 "mime_type": item.mime_type, "size": item.size} for item in rows]

    def excel_attachment(self, batch_id: str | None) -> dict | None:
        if not batch_id:
            return None
        row = self.db.execute(select(ExcelBatch, FileObject).join(FileObject, FileObject.id == ExcelBatch.file_id)
                              .where(ExcelBatch.id == batch_id)).first()
        if row is None:
            return None
        batch, item = row
        return {"batch_id": batch.id, "file_id": item.id, "url": item.url, "original_name": batch.original_name,
                "mime_type": item.mime_type, "size": item.size, "status": batch.status, "total_rows": batch.total_rows}

    def parts(self, ticket_id: str) -> list[dict]:
        rows = self.db.execute(select(ManualTicketPart, Part).join(Part, Part.id == ManualTicketPart.part_id)
                               .where(ManualTicketPart.ticket_id == ticket_id)
                               .order_by(ManualTicketPart.created_at, ManualTicketPart.id)).all()
        return [{"part_id": p.id, "part_no": p.part_no, "brand": p.brand, "name": p.name_zh, "quantity": i.quantity,
                 "confidence": float(i.confidence) if i.confidence is not None else None, "reason": i.reason}
                for i, p in rows]

    def timeline(self, ticket_id: str) -> list[dict]:
        rows = self.db.execute(select(ManualTicketEvent, AdminUser.username).outerjoin(
            AdminUser, AdminUser.id == ManualTicketEvent.actor_id).where(ManualTicketEvent.ticket_id == ticket_id)
            .order_by(ManualTicketEvent.created_at, ManualTicketEvent.id)).all()
        return [{"id": event.id, "event_type": event.event_type, "actor_id": event.actor_id,
                 "actor_name": username, "status_from": event.status_from, "status_to": event.status_to,
                 "content": event.content, "created_at": event.created_at.isoformat()} for event, username in rows]

    def serialize(self, ticket: ManualTicket, *, admin: bool = False) -> dict:
        return {"id": ticket.id, "ticket_no": ticket.ticket_no, "status": ticket.status,
                "contact_name": ticket.contact_name,
                "contact_info": ticket.contact_value if admin else self.mask_contact(ticket.contact_value),
                "country": ticket.country, "communication_tool": ticket.communication_tool,
                "machine_type": ticket.machine_type, "machine_brand": ticket.machine_brand,
                "machine_model": ticket.machine_model, "serial_no": ticket.serial_no,
                "engine_model": ticket.engine_model, "part_description": ticket.query_text,
                "quantity": ticket.quantity, "note": ticket.note, "ai_preliminary_result": ticket.ai_preliminary_result,
                "excel_batch_id": ticket.excel_batch_id, "excel_attachment": self.excel_attachment(ticket.excel_batch_id),
                "assignee_id": ticket.assignee_id,
                "assignee_name": self.db.scalar(select(AdminUser.username).where(AdminUser.id == ticket.assignee_id)) if ticket.assignee_id else None,
                "match_evidence": ticket.match_evidence, "internal_note": ticket.internal_note if admin else None,
                "attachments": self.attachments(ticket.id), "resolved_parts": self.parts(ticket.id),
                "timeline": self.timeline(ticket.id) if admin else [],
                "created_at": ticket.created_at.isoformat(), "updated_at": ticket.updated_at.isoformat()}

    def serialize_status(self, ticket: ManualTicket) -> dict:
        return {"ticket_no": ticket.ticket_no, "status": ticket.status,
                "contact_info": self.mask_contact(ticket.contact_value),
                "communication_tool": ticket.communication_tool,
                "resolved_parts": self.parts(ticket.id),
                "updated_at": ticket.updated_at.isoformat()}

    def list_admin(self, *, status=None, assignee_id=None, date_from=None, date_to=None, machine_brand=None,
                   page=1, page_size=20, sort="priority", order="asc") -> dict:
        filters = []
        if status: filters.append(ManualTicket.status == status)
        if assignee_id: filters.append(ManualTicket.assignee_id == assignee_id)
        if date_from: filters.append(ManualTicket.created_at >= date_from)
        if date_to: filters.append(ManualTicket.created_at <= date_to)
        if machine_brand: filters.append(ManualTicket.machine_brand.ilike(f"%{machine_brand}%"))
        total = self.db.scalar(select(func.count()).select_from(ManualTicket).where(*filters)) or 0
        priority = case({"pending": 0, "processing": 1, "need_info": 2, "matched": 3, "in_cart": 4, "closed": 5},
                        value=ManualTicket.status, else_=6)
        order_col = priority if sort == "priority" else getattr(ManualTicket, sort)
        order_clause = order_col.desc() if order == "desc" else order_col.asc()
        query = select(ManualTicket).where(*filters).order_by(order_clause, ManualTicket.created_at.asc(), ManualTicket.id)
        items = self.db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [self.serialize(item, admin=True) for item in items], "total": total,
                "page": page, "page_size": page_size}

    def options(self) -> dict:
        users = self.db.scalars(select(AdminUser).where(AdminUser.is_active.is_(True),
            AdminUser.role.in_({"operator", "admin"})).order_by(AdminUser.username)).all()
        brands = self.db.scalars(select(ManualTicket.machine_brand).where(ManualTicket.machine_brand.is_not(None))
                                 .distinct().order_by(ManualTicket.machine_brand)).all()
        return {"assignees": [{"id": user.id, "username": user.username, "role": user.role} for user in users],
                "brands": brands}

    def stats(self) -> dict:
        pending = self.db.scalar(select(func.count()).select_from(ManualTicket).where(ManualTicket.status == "pending")) or 0
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_new = self.db.scalar(select(func.count()).select_from(ManualTicket).where(ManualTicket.created_at >= start)) or 0
        completed = self.db.scalars(select(ManualTicket).where(ManualTicket.status.in_({"matched", "in_cart", "closed"}))).all()
        durations = []
        for item in completed:
            created, updated = item.created_at, item.updated_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            durations.append(max(0, (updated - created).total_seconds()))
        return {"pending_count": pending, "today_new": today_new,
                "average_handling_seconds": round(sum(durations) / len(durations)) if durations else 0}
