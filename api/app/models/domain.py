from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class Part(IdMixin, TimestampMixin, Base):
    __tablename__ = "part"
    __table_args__ = (
        UniqueConstraint("brand", "part_no"),
        CheckConstraint("price IS NULL OR price >= 0", name="part_price_nonnegative"),
        CheckConstraint("stock >= 0", name="part_stock_nonnegative"),
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    part_no: Mapped[str] = mapped_column(String(150), index=True)
    oem_no: Mapped[str | None] = mapped_column(String(150), index=True)
    alternate_no: Mapped[str | None] = mapped_column(String(150), index=True)
    brand: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    name_zh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_vi: Mapped[str | None] = mapped_column(String(255))
    specs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    stock_status: Mapped[str] = mapped_column(String(30), default="in_stock", index=True)
    unit: Mapped[str] = mapped_column(String(30), default="件")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class PartCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "part_category"
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("part_category.id", ondelete="RESTRICT"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class PartImage(IdMixin, TimestampMixin, Base):
    __tablename__ = "part_image"
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(String(36), index=True)
    url: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    image_type: Mapped[str] = mapped_column(String(30), default="product")


class Machine(IdMixin, TimestampMixin, Base):
    __tablename__ = "machine"
    machine_type: Mapped[str] = mapped_column(String(100), index=True)
    brand: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str] = mapped_column(String(150), index=True)
    series: Mapped[str | None] = mapped_column(String(150))
    year: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(100))
    engine_model: Mapped[str | None] = mapped_column(String(150), index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class MachineType(IdMixin, TimestampMixin, Base):
    __tablename__ = "machine_type"
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MachinePartRelation(IdMixin, TimestampMixin, Base):
    __tablename__ = "machine_part_relation"
    __table_args__ = (
        UniqueConstraint("machine_id", "part_id"),
        CheckConstraint("priority >= 0", name="machine_part_priority_nonnegative"),
    )
    machine_id: Mapped[str] = mapped_column(ForeignKey("machine.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    system: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100))
    serial_from: Mapped[str | None] = mapped_column(String(100))
    serial_to: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class PartCrossReference(IdMixin, TimestampMixin, Base):
    __tablename__ = "part_cross_reference"
    __table_args__ = (
        CheckConstraint("source_part_id <> target_part_id", name="cross_ref_distinct_parts"),
        CheckConstraint("reliability >= 0 AND reliability <= 1", name="cross_ref_reliability_range"),
        CheckConstraint("priority >= 0", name="cross_ref_priority_nonnegative"),
        CheckConstraint("status IN ('pending', 'active', 'inactive', 'rejected')", name="cross_ref_status_valid"),
    )
    source_part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    target_part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(50), default="replacement")
    reliability: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1)
    restrictions: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class PartAlias(IdMixin, TimestampMixin, Base):
    __tablename__ = "part_alias"
    __table_args__ = (UniqueConstraint("part_id", "alias", "language"),)
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    language: Mapped[str] = mapped_column(String(10), default="zh")
    region: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class CartItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "cart_item"
    __table_args__ = (
        UniqueConstraint("owner_key", "part_id"),
        CheckConstraint("quantity > 0", name="cart_item_quantity_positive"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="cart_item_confidence_range"),
    )
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    match_status: Mapped[str] = mapped_column(String(30), default="exact")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    source: Mapped[str] = mapped_column(String(30), default="direct")
    need_confirm: Mapped[bool] = mapped_column(Boolean, default=False)
    query_id: Mapped[str | None] = mapped_column(ForeignKey("part_query_log.id", ondelete="SET NULL"), index=True)


class InquiryOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "inquiry_order"
    __table_args__ = (
        CheckConstraint("total_quantity > 0", name="inquiry_order_quantity_positive"),
        CheckConstraint("total_amount >= 0", name="inquiry_order_amount_nonnegative"),
    )
    order_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    contact_name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    contact_method: Mapped[str] = mapped_column(String(255))
    communication_tool: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    total_quantity: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class InquiryOrderItem(IdMixin, Base):
    __tablename__ = "inquiry_order_item"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="inquiry_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="inquiry_order_item_price_nonnegative"),
        CheckConstraint("subtotal >= 0", name="inquiry_order_item_subtotal_nonnegative"),
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("inquiry_order.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[str | None] = mapped_column(ForeignKey("part.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualTicket(IdMixin, TimestampMixin, Base):
    __tablename__ = "manual_ticket"
    ticket_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    owner_key: Mapped[str | None] = mapped_column(String(140), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_value: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    communication_tool: Mapped[str | None] = mapped_column(String(30))
    machine_type: Mapped[str | None] = mapped_column(String(100))
    machine_brand: Mapped[str | None] = mapped_column(String(100), index=True)
    machine_model: Mapped[str | None] = mapped_column(String(150))
    serial_no: Mapped[str | None] = mapped_column(String(150))
    engine_model: Mapped[str | None] = mapped_column(String(150))
    query_text: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(Text)
    ai_preliminary_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extracted_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    excel_batch_id: Mapped[str | None] = mapped_column(String(36), index=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"), index=True)
    match_evidence: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    result_part_id: Mapped[str | None] = mapped_column(ForeignKey("part.id", ondelete="SET NULL"))


class ManualTicketAttachment(IdMixin, Base):
    __tablename__ = "manual_ticket_attachment"
    __table_args__ = (UniqueConstraint("ticket_id", "file_id"),)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("file_object.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualTicketPart(IdMixin, Base):
    __tablename__ = "manual_ticket_part"
    __table_args__ = (
        UniqueConstraint("ticket_id", "part_id"),
        CheckConstraint("quantity > 0", name="manual_ticket_part_quantity_positive"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="manual_ticket_part_confidence_range"),
    )
    ticket_id: Mapped[str] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualTicketSupplement(IdMixin, Base):
    __tablename__ = "manual_ticket_supplement"
    ticket_id: Mapped[str] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualTicketEvent(IdMixin, Base):
    __tablename__ = "manual_ticket_event"
    ticket_id: Mapped[str] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    status_from: Mapped[str | None] = mapped_column(String(30))
    status_to: Mapped[str | None] = mapped_column(String(30))
    content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class KnowledgeCandidate(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_candidate"
    __table_args__ = (CheckConstraint(
        "(ticket_id IS NOT NULL AND query_correction_id IS NULL) OR "
        "(ticket_id IS NULL AND query_correction_id IS NOT NULL)",
        name="knowledge_candidate_single_source",
    ),)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), unique=True, index=True)
    query_correction_id: Mapped[str | None] = mapped_column(
        ForeignKey("query_log_correction.id", ondelete="CASCADE"), unique=True, index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", index=True)


class ManualTicketCartAddition(IdMixin, Base):
    __tablename__ = "manual_ticket_cart_addition"
    __table_args__ = (UniqueConstraint("ticket_id", "owner_key"),)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("manual_ticket.id", ondelete="CASCADE"), index=True)
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PartQueryLog(IdMixin, Base):
    __tablename__ = "part_query_log"
    __table_args__ = (UniqueConstraint("query_type", "source_id"),)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), index=True)
    query_type: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[str | None] = mapped_column(String(36), index=True)
    query_text: Mapped[str | None] = mapped_column(Text)
    request_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extracted_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ai_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    match_status: Mapped[str | None] = mapped_column(String(30), index=True)
    need_manual: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class QueryLogCorrection(IdMixin, Base):
    __tablename__ = "query_log_correction"
    __table_args__ = (CheckConstraint("length(trim(reason)) >= 3", name="query_log_correction_reason"),)
    query_log_id: Mapped[str] = mapped_column(
        ForeignKey("part_query_log.id", ondelete="CASCADE"), unique=True, index=True,
    )
    recommended_part_id: Mapped[str | None] = mapped_column(ForeignKey("part.id", ondelete="RESTRICT"), index=True)
    correct_part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("admin_user.id", ondelete="SET NULL"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AiMatchEvidence(IdMixin, Base):
    __tablename__ = "ai_match_evidence"
    query_log_id: Mapped[str] = mapped_column(ForeignKey("part_query_log.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[str] = mapped_column(ForeignKey("part.id", ondelete="CASCADE"), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[Any] = mapped_column(JSON, default=list)


class LlmCallLog(IdMixin, Base):
    __tablename__ = "llm_call_log"
    query_log_id: Mapped[str | None] = mapped_column(ForeignKey("part_query_log.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    api_mode: Mapped[str] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_hash: Mapped[str] = mapped_column(String(64), index=True)
    safety_identifier: Mapped[str] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True)
    error_type: Mapped[str | None] = mapped_column(String(50), index=True)
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AiRateLimitEvent(IdMixin, Base):
    __tablename__ = "ai_rate_limit_event"
    client_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SysConfig(TimestampMixin, Base):
    __tablename__ = "sys_configs"
    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    value_type: Mapped[str] = mapped_column(String(20), default="json")
    description: Mapped[str | None] = mapped_column(String(500))
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)


class AdminRefreshToken(IdMixin, Base):
    __tablename__ = "admin_refresh_token"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("admin_user.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LanguagePreference(IdMixin, TimestampMixin, Base):
    __tablename__ = "language_preference"
    __table_args__ = (
        UniqueConstraint("owner_key"),
        CheckConstraint("language IN ('zh', 'en', 'vi')", name="language_preference_supported"),
    )
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    language: Mapped[str] = mapped_column(String(10))


class FileObject(IdMixin, Base):
    __tablename__ = "file_object"
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    owner_key: Mapped[str | None] = mapped_column(String(140), index=True)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_lines: Mapped[list[str] | None] = mapped_column(JSON)
    image_type: Mapped[str | None] = mapped_column(String(40))
    extracted_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExcelBatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "excel_batch"
    __table_args__ = (CheckConstraint("total_rows >= 0 AND total_rows <= 500", name="excel_batch_row_limit"),)
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("file_object.id", ondelete="RESTRICT"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    duplicate_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class ExcelBatchRow(IdMixin, TimestampMixin, Base):
    __tablename__ = "excel_batch_row"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_index"),
        CheckConstraint("row_index > 0", name="excel_batch_row_index_positive"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="excel_batch_row_quantity_positive"),
    )
    batch_id: Mapped[str] = mapped_column(ForeignKey("excel_batch.id", ondelete="CASCADE"), index=True)
    row_index: Mapped[int] = mapped_column(Integer)
    raw_content: Mapped[dict[str, Any]] = mapped_column(JSON)
    normalized_content: Mapped[dict[str, Any]] = mapped_column(JSON)
    quantity: Mapped[int | None] = mapped_column(Integer)
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    match_status: Mapped[str | None] = mapped_column(String(30), index=True)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    match_reason: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(String(30))
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("manual_ticket.id", ondelete="SET NULL"), unique=True)


class ExcelBatchJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "excel_batch_job"
    __table_args__ = (CheckConstraint("attempts >= 0", name="excel_batch_job_attempts_nonnegative"),)
    batch_id: Mapped[str] = mapped_column(ForeignKey("excel_batch.id", ondelete="CASCADE"), index=True)
    owner_key: Mapped[str] = mapped_column(String(140), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminUser(IdMixin, TimestampMixin, Base):
    __tablename__ = "admin_user"
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


Index("ix_cross_ref_pair", PartCrossReference.source_part_id, PartCrossReference.target_part_id, unique=True)
Index("uq_part_part_no", Part.part_no, unique=True)
Index("ix_machine_brand_model", Machine.brand, Machine.model)
Index("ix_part_active_category", Part.is_active, Part.category)
