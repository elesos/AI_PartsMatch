#!/usr/bin/env python3
"""Idempotently load a compact, searchable demonstration catalogue."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_, select

from app.core.database import SessionLocal
from app.models import Machine, MachinePartRelation, Part, PartAlias, PartCategory, PartCrossReference

BRANDS = {
    "Toyota": {"prefix": "TY", "machine_type": "forklift", "model": "8FD30", "name": "丰田叉车"},
    "CAT": {"prefix": "CAT", "machine_type": "excavator", "model": "320D", "name": "卡特挖掘机"},
    "Heli": {"prefix": "HL", "machine_type": "forklift", "model": "CPCD30", "name": "合力叉车"},
}
PART_NAMES = [
    ("空气滤芯", "Air filter", "engine"), ("机油滤芯", "Oil filter", "engine"),
    ("燃油滤芯", "Fuel filter", "engine"), ("液压滤芯", "Hydraulic filter", "hydraulic"),
    ("水泵", "Water pump", "cooling"), ("风扇皮带", "Fan belt", "engine"),
    ("制动片", "Brake pad", "brake"), ("起动机", "Starter motor", "electrical"),
    ("发电机", "Alternator", "electrical"), ("密封修理包", "Seal kit", "hydraulic"),
]
CATEGORIES = [
    ("发动机系统", "engine", None), ("液压系统", "hydraulic", None),
    ("制动系统", "brake", None), ("电气系统", "electrical", None),
    ("冷却系统", "cooling", "engine"),
]


def get_or_create(db, model, defaults: dict | None = None, **lookup):
    item = db.scalar(select(model).filter_by(**lookup))
    if item is None:
        item = model(**lookup, **(defaults or {}))
        db.add(item)
        db.flush()
    return item


def seed() -> dict[str, int]:
    counts = {"categories": 0, "machines": 0, "parts": 0, "relations": 0, "cross_refs": 0}
    with SessionLocal.begin() as db:
        categories: dict[str, PartCategory] = {}
        for name, slug, parent_slug in CATEGORIES:
            parent = categories.get(parent_slug) if parent_slug else None
            before = db.scalar(select(PartCategory.id).where(PartCategory.slug == slug))
            category = get_or_create(
                db, PartCategory, {"name": name, "parent_id": parent.id if parent else None,
                                   "sort_order": len(categories), "is_active": True}, slug=slug,
            )
            categories[slug] = category
            counts["categories"] += int(before is None)

        for brand, spec in BRANDS.items():
            machine = db.scalar(select(Machine).where(
                Machine.brand == brand, Machine.model == spec["model"], Machine.machine_type == spec["machine_type"]
            ))
            if machine is None:
                machine = Machine(machine_type=spec["machine_type"], brand=brand, model=spec["model"],
                                  series="demo", year=2024, region="global", engine_model=f"{spec['prefix']}-ENG")
                db.add(machine)
                db.flush()
                counts["machines"] += 1

            parts: list[Part] = []
            for index, (name_zh, name_en, category) in enumerate(PART_NAMES, 1):
                part_no = f"{spec['prefix']}-{index:04d}"
                part = db.scalar(select(Part).where(Part.brand == brand, Part.part_no == part_no))
                if part is None:
                    part = Part(
                        sku=f"{spec['prefix']}-SKU-{index:04d}", part_no=part_no,
                        oem_no=f"OEM-{spec['prefix']}-{index:04d}", brand=brand, category=category,
                        name_zh=f"{spec['name']}{name_zh}", name_en=f"{brand} {name_en}",
                        name_vi=None, specs={"demo": True, "position": index},
                        price=Decimal("10.00") * index, stock=20 + index, is_active=True,
                    )
                    db.add(part)
                    db.flush()
                    counts["parts"] += 1
                parts.append(part)
                if db.scalar(select(PartAlias.id).where(
                    PartAlias.part_id == part.id, PartAlias.alias == name_zh, PartAlias.language == "zh"
                )) is None:
                    db.add(PartAlias(part_id=part.id, alias=name_zh, language="zh", source="seed", status="active"))
                if db.scalar(select(MachinePartRelation.id).where(
                    MachinePartRelation.machine_id == machine.id, MachinePartRelation.part_id == part.id
                )) is None:
                    db.add(MachinePartRelation(machine_id=machine.id, part_id=part.id, system=category,
                                               position="standard", notes="seed demo fitment", priority=10))
                    counts["relations"] += 1

            for left, right in ((0, 1), (2, 3), (4, 5)):
                source, target = parts[left], parts[right]
                existing = db.scalar(select(PartCrossReference.id).where(or_(
                    (PartCrossReference.source_part_id == source.id) & (PartCrossReference.target_part_id == target.id),
                    (PartCrossReference.source_part_id == target.id) & (PartCrossReference.target_part_id == source.id),
                )))
                if existing is None:
                    db.add(PartCrossReference(source_part_id=source.id, target_part_id=target.id,
                                              relation_type="replacement", reliability=Decimal("0.9500"),
                                              restrictions="Demo data; verify serial range"))
                    counts["cross_refs"] += 1
    return counts


if __name__ == "__main__":
    result = seed()
    print("Seed complete: " + ", ".join(f"{key}={value}" for key, value in result.items()))
