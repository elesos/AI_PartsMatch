from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Machine, MachinePartRelation, Part, PartAlias, PartCategory,
    PartCrossReference, PartImage,
)
from app.schemas.search import SearchCandidate, SearchResult
from app.services.catalog_validation import normalize_part_number
from app.services.i18n import localized_name


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PartSearchService:
    """Deterministic M2 catalogue search. AI enrichment is deliberately left to M6."""

    def __init__(self, db: Session, lang: str = "zh") -> None:
        self.db = db
        self.lang = lang

    def _images(self, part_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not part_ids:
            return {}
        rows = self.db.scalars(
            select(PartImage).where(PartImage.part_id.in_(part_ids)).order_by(
                PartImage.part_id, PartImage.sort_order, PartImage.created_at
            )
        )
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for image in rows:
            result[image.part_id].append({
                "id": image.id, "file_id": image.file_id, "url": image.url,
                "sort_order": image.sort_order,
            })
        return result

    def _fitments(self, part_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not part_ids:
            return {}
        rows = self.db.execute(
            select(MachinePartRelation, Machine).join(
                Machine, Machine.id == MachinePartRelation.machine_id
            ).where(MachinePartRelation.part_id.in_(part_ids), MachinePartRelation.is_active.is_(True)).order_by(
                MachinePartRelation.priority.desc(), Machine.brand, Machine.model
            )
        )
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation, machine in rows:
            result[relation.part_id].append({
                "machine_id": machine.id, "machine_type": machine.machine_type,
                "brand": machine.brand, "model": machine.model,
                "engine_model": machine.engine_model, "system": relation.system,
                "position": relation.position, "serial_from": relation.serial_from,
                "serial_to": relation.serial_to, "notes": relation.notes,
            })
        return result

    def _candidates(
        self, parts: list[Part], confidence: float, reason: str,
        *, evidence: list[dict[str, Any] | str] | None = None,
        relation_data: dict[str, tuple[str, float]] | None = None,
        fitments: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[SearchCandidate]:
        images = self._images([part.id for part in parts])
        resolved_fitments = fitments if fitments is not None else self._fitments([part.id for part in parts])
        candidates = []
        for part in parts:
            relation_type, reliability = (relation_data or {}).get(part.id, (None, None))
            part_data = {
                "id": part.id, "sku": part.sku, "part_no": part.part_no,
                "oem_no": part.oem_no, "brand": part.brand, "category": part.category,
                "name": localized_name(part, self.lang),
                "name_zh": part.name_zh, "name_en": part.name_en, "name_vi": part.name_vi,
                "specs": part.specs or {}, "price": float(part.price) if part.price is not None else None,
                "stock": part.stock, "images": images.get(part.id, []),
            }
            part_fitments = resolved_fitments.get(part.id, [])
            candidates.append(SearchCandidate(
                part=part_data, confidence=reliability if reliability is not None else confidence,
                reason=reason, evidence=evidence or [], relation_type=relation_type,
                reliability=reliability, fitments=part_fitments,
                requires_serial_confirmation=any(
                    f.get("serial_from") is not None or f.get("serial_to") is not None
                    for f in part_fitments
                ),
            ))
        return candidates

    def part_number(self, query: str) -> SearchResult:
        normalized = normalize_part_number(query)
        parts = list(self.db.scalars(select(Part).where(
            Part.is_active.is_(True), Part.part_no == normalized
        ).limit(2)))
        candidates = self._candidates(
            parts, 1.0, "配件编号精确匹配", evidence=[{"field": "part_no", "value": normalized}]
        )
        return SearchResult(
            query_type="part_no", extracted_info={"part_no": normalized},
            match_status="exact" if len(parts) == 1 else ("multiple" if parts else "not_found"),
            candidates=candidates,
            suggestions=[] if parts else ["检查配件编号", "尝试 OEM 编号"],
        )

    def oem(self, query: str) -> SearchResult:
        normalized = normalize_part_number(query)
        originals = list(self.db.scalars(select(Part).where(
            Part.is_active.is_(True), Part.oem_no == normalized
        ).order_by(Part.brand, Part.part_no)))
        if not originals:
            return SearchResult(
                query_type="oem", extracted_info={"oem_no": normalized}, match_status="not_found",
                suggestions=["检查 OEM 编号", "尝试配件编号"],
            )

        original_ids = [part.id for part in originals]
        references = list(self.db.scalars(select(PartCrossReference).where(
            PartCrossReference.status == "active",
            or_(
                PartCrossReference.source_part_id.in_(original_ids),
                PartCrossReference.target_part_id.in_(original_ids),
            ),
        )))
        alternate_data: dict[str, tuple[str, float]] = {}
        for reference in references:
            alternate_id = (
                reference.target_part_id if reference.source_part_id in original_ids
                else reference.source_part_id
            )
            value = (reference.relation_type, float(reference.reliability))
            previous = alternate_data.get(alternate_id)
            if previous is None or value[1] > previous[1]:
                alternate_data[alternate_id] = value
        alternates = list(self.db.scalars(select(Part).where(
            Part.id.in_(alternate_data), Part.is_active.is_(True)
        ).order_by(Part.brand, Part.part_no))) if alternate_data else []
        relation_data = {part.id: ("OEM", 1.0) for part in originals} | alternate_data
        candidates = self._candidates(
            originals + alternates, 1.0, "OEM 编号及双向替代关系匹配",
            evidence=[{"field": "oem_no", "value": normalized}], relation_data=relation_data,
        )
        return SearchResult(
            query_type="oem", extracted_info={"oem_no": normalized},
            match_status="exact" if len(candidates) == 1 else "multiple", candidates=candidates,
        )

    def machine(self, brand: str, model: str | None) -> SearchResult:
        brand_value, model_value = brand.strip(), (model or "").strip()
        statement = select(Machine).where(func.upper(Machine.brand) == brand_value.upper())
        if model_value:
            statement = statement.where(func.upper(Machine.model) == model_value.upper())
        machines = list(self.db.scalars(statement.order_by(Machine.model)))
        extracted = {"machine_brand": brand_value, "machine_model": model_value or None}
        if not machines:
            return SearchResult(
                query_type="machine", extracted_info=extracted, match_status="not_found",
                category_navigation=self.category_navigation(),
                suggestions=["检查设备品牌和型号", "仅输入品牌浏览分类"],
            )
        machine_ids = [machine.id for machine in machines]
        rows = list(self.db.execute(
            select(Part, MachinePartRelation, Machine).join(
                MachinePartRelation, MachinePartRelation.part_id == Part.id
            ).join(Machine, Machine.id == MachinePartRelation.machine_id).where(
                MachinePartRelation.machine_id.in_(machine_ids), MachinePartRelation.is_active.is_(True), Part.is_active.is_(True)
            ).order_by(MachinePartRelation.priority.desc(), Part.part_no)
        ))
        parts, fitments, groups = [], defaultdict(list), defaultdict(list)
        seen: set[str] = set()
        for part, relation, machine in rows:
            if part.id not in seen:
                parts.append(part)
                groups[relation.system or part.category or "other"].append(part.id)
                seen.add(part.id)
            fitments[part.id].append({
                "machine_id": machine.id, "machine_type": machine.machine_type,
                "brand": machine.brand, "model": machine.model, "engine_model": machine.engine_model,
                "system": relation.system, "position": relation.position,
                "serial_from": relation.serial_from, "serial_to": relation.serial_to,
                "notes": relation.notes,
            })
        return SearchResult(
            query_type="machine", extracted_info=extracted,
            match_status="exact" if model_value and len(machines) == 1 else ("multiple" if parts else "insufficient"),
            candidates=self._candidates(parts, 0.98 if model_value else 0.85, "设备适配关系匹配", fitments=fitments),
            groups=dict(groups), category_navigation=[] if parts else self.category_navigation(),
            suggestions=[] if parts else ["当前设备暂无精确配件，请按分类浏览"],
        )

    def engine(self, query: str) -> SearchResult:
        engine_model = query.strip()
        machines = list(self.db.scalars(select(Machine).where(
            func.upper(Machine.engine_model) == engine_model.upper()
        )))
        if not machines:
            return SearchResult(
                query_type="engine", extracted_info={"engine_model": engine_model}, match_status="not_found",
                suggestions=["检查发动机型号", "补充整机品牌和型号"],
            )
        rows = list(self.db.execute(
            select(Part, MachinePartRelation, Machine).join(
                MachinePartRelation, MachinePartRelation.part_id == Part.id
            ).join(Machine, Machine.id == MachinePartRelation.machine_id).where(
                MachinePartRelation.machine_id.in_([m.id for m in machines]),
                MachinePartRelation.is_active.is_(True),
                Part.is_active.is_(True),
                or_(func.lower(MachinePartRelation.system) == "engine", func.lower(Part.category) == "engine"),
            ).order_by(MachinePartRelation.priority.desc(), Part.part_no)
        ))
        parts, fitments, seen = [], defaultdict(list), set()
        for part, relation, machine in rows:
            if part.id not in seen:
                parts.append(part)
                seen.add(part.id)
            fitments[part.id].append({
                "machine_id": machine.id, "machine_type": machine.machine_type,
                "brand": machine.brand, "model": machine.model, "engine_model": machine.engine_model,
                "system": relation.system, "position": relation.position,
                "serial_from": relation.serial_from, "serial_to": relation.serial_to,
                "notes": relation.notes,
            })
        candidates = self._candidates(parts, 0.9, "发动机型号及发动机系统适配关系匹配", fitments=fitments)
        return SearchResult(
            query_type="engine", extracted_info={"engine_model": engine_model},
            match_status="high" if candidates else "insufficient", candidates=candidates,
            suggestions=["提供设备序列号可进一步确认适配范围"],
        )

    def text(self, query: str, lang: str) -> SearchResult:
        self.lang = lang
        keyword = query.strip()
        if len(keyword) < 2:
            return SearchResult(
                query_type="natural", extracted_info={"keyword": keyword, "lang": lang},
                match_status="insufficient", suggestions=["请输入至少 2 个字符", "补充品牌或型号"],
            )
        pattern = f"%{_escape_like(keyword)}%"
        language_order = list(dict.fromkeys((lang, "en", "zh")))
        name_columns = [{"zh": Part.name_zh, "en": Part.name_en, "vi": Part.name_vi}[code]
                        for code in language_order]
        name_column = name_columns[0]
        alias_ids = select(PartAlias.part_id).where(
            PartAlias.status == "active", PartAlias.language.in_(language_order),
            PartAlias.alias.ilike(pattern, escape="\\"),
        )
        parts = list(self.db.scalars(select(Part).where(
            Part.is_active.is_(True),
            or_(*(column.ilike(pattern, escape="\\") for column in name_columns), Part.id.in_(alias_ids)),
        ).order_by(
            case((func.lower(name_column) == keyword.lower(), 0), else_=1), Part.part_no
        ).limit(50)))
        lowered = keyword.casefold()
        aliases = self.db.execute(select(PartAlias.part_id, PartAlias.alias, PartAlias.language).where(
            PartAlias.part_id.in_([p.id for p in parts]), PartAlias.status == "active",
            PartAlias.language.in_(language_order),
        )) if parts else []
        aliases_by_part: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for part_id, alias, alias_lang in aliases:
            aliases_by_part[part_id].append((alias, alias_lang))
        scores: dict[str, float] = {}
        for part in parts:
            requested_name = (getattr(part, f"name_{lang}") or "").casefold()
            localized = localized_name(part, lang).casefold()
            requested_aliases = [value.casefold() for value, code in aliases_by_part[part.id] if code == lang]
            fallback_aliases = [value.casefold() for value, code in aliases_by_part[part.id] if code != lang]
            if requested_name == lowered or lowered in requested_aliases:
                scores[part.id] = 1.0
            elif localized == lowered or lowered in fallback_aliases:
                scores[part.id] = 0.9
            elif requested_name.startswith(lowered):
                scores[part.id] = 0.85
            else:
                scores[part.id] = 0.7
        parts.sort(key=lambda p: (-scores[p.id], p.part_no))
        candidates = []
        for part in parts:
            matched_aliases = [a for a, _code in aliases_by_part[part.id] if lowered in a.casefold()]
            candidates.extend(self._candidates(
                [part], scores[part.id], "配件名称或已审核别名匹配",
                evidence=[{"field": "alias" if matched_aliases else f"name_{lang}",
                           "value": matched_aliases[0] if matched_aliases else localized_name(part, lang)}],
            ))
        return SearchResult(
            query_type="natural", extracted_info={"keyword": keyword, "lang": lang},
            match_status=("exact" if len(parts) == 1 and scores[parts[0].id] == 1 else
                          "multiple" if len(parts) > 1 else "high" if parts else "not_found"),
            candidates=candidates,
            suggestions=[] if parts else ["尝试更短的配件名称", "补充品牌或设备型号"],
        )

    def category_navigation(self) -> list[dict[str, Any]]:
        categories = list(self.db.scalars(select(PartCategory).where(
            PartCategory.is_active.is_(True)
        ).order_by(PartCategory.sort_order, PartCategory.name)))
        by_parent: dict[str | None, list[PartCategory]] = defaultdict(list)
        for category in categories:
            by_parent[category.parent_id].append(category)
        counts = {category: count for category, count in self.db.execute(
            select(Part.category, func.count(Part.id)).where(
                Part.is_active.is_(True)
            ).group_by(Part.category)
        )}
        return [{
            "id": root.id, "name": root.name, "slug": root.slug,
            "part_count": int(counts.get(root.slug, 0)),
            "children": [{
                "id": child.id, "name": child.name, "slug": child.slug,
                "part_count": int(counts.get(child.slug, 0)),
            } for child in by_parent.get(root.id, [])],
        } for root in by_parent.get(None, [])]

    def part_detail(self, part_id: str) -> dict[str, Any] | None:
        part = self.db.scalar(select(Part).where(Part.id == part_id, Part.is_active.is_(True)))
        if part is None:
            return None
        candidate = self._candidates([part], 1, "配件详情")[0]
        references = list(self.db.scalars(select(PartCrossReference).where(
            PartCrossReference.status == "active",
            or_(
                PartCrossReference.source_part_id == part_id,
                PartCrossReference.target_part_id == part_id,
            ),
        )))
        alternate_ids = [
            r.target_part_id if r.source_part_id == part_id else r.source_part_id for r in references
        ]
        alternates = {p.id: p for p in self.db.scalars(select(Part).where(
            Part.id.in_(alternate_ids), Part.is_active.is_(True)
        ))} if alternate_ids else {}
        replacements = []
        for reference in references:
            alternate_id = reference.target_part_id if reference.source_part_id == part_id else reference.source_part_id
            alternate = alternates.get(alternate_id)
            if alternate:
                replacements.append({
                    "part": self._candidates([alternate], float(reference.reliability), "双向替代关系")[0].part.model_dump(),
                    "relation_type": reference.relation_type,
                    "reliability": float(reference.reliability), "restrictions": reference.restrictions,
                })
        data = candidate.part.model_dump()
        data.update({
            "is_active": True, "created_at": part.created_at, "updated_at": part.updated_at,
            "fitments": candidate.fitments,
            "machines": candidate.fitments,
            "engines": sorted({f["engine_model"] for f in candidate.fitments if f.get("engine_model")}),
            "alternatives": replacements,
        })
        return data

    def hot_machines(self, limit: int) -> list[dict[str, Any]]:
        relation_count = func.count(MachinePartRelation.id)
        rows = self.db.execute(select(Machine, relation_count.label("part_count")).join(
            MachinePartRelation, MachinePartRelation.machine_id == Machine.id
        ).join(Part, Part.id == MachinePartRelation.part_id).where(
            Part.is_active.is_(True), MachinePartRelation.is_active.is_(True)
        ).group_by(Machine.id).order_by(relation_count.desc(), Machine.brand, Machine.model).limit(limit))
        return [{
            "id": machine.id, "machine_type": machine.machine_type, "brand": machine.brand,
            "model": machine.model, "series": machine.series, "engine_model": machine.engine_model,
            "part_count": count,
        } for machine, count in rows]

    def hot_parts(self, limit: int) -> list[dict[str, Any]]:
        relation_count = func.count(MachinePartRelation.id)
        rows = self.db.execute(select(Part, relation_count.label("fitment_count")).outerjoin(
            MachinePartRelation, and_(MachinePartRelation.part_id == Part.id, MachinePartRelation.is_active.is_(True))
        ).where(Part.is_active.is_(True)).group_by(Part.id).order_by(
            relation_count.desc(), Part.stock.desc(), Part.part_no
        ).limit(limit))
        parts_and_counts = list(rows)
        candidates = self._candidates([part for part, _ in parts_and_counts], 1, "热门配件")
        return [candidate.part.model_dump() | {"fitment_count": count}
                for candidate, (_, count) in zip(candidates, parts_and_counts)]
