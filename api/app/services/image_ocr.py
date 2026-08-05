from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol

import httpx
import pytesseract
from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import AiMatchEvidence, FileObject, PartQueryLog
from app.services.config_service import ConfigService
from app.services.part_search import PartSearchService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OCRPayload:
    text: str
    lines: list[str]
    blur_score: float = 1.0


class OCRProvider(Protocol):
    async def recognize(self, content: bytes, mime_type: str, image_id: str) -> OCRPayload: ...


class MockOCRProvider:
    """Deterministic test-only provider configured in sys_configs."""

    def __init__(self, configs: ConfigService) -> None:
        self.configs = configs

    async def recognize(self, content: bytes, mime_type: str, image_id: str) -> OCRPayload:
        if mime_type in {"image/heic", "image/heif"}:
            raise AppError(
                "the test-only mock does not decode HEIC; use local_tesseract or a HEIC-capable HTTP provider",
                code="HEIC_OCR_UNSUPPORTED", status_code=422,
            )
        configured = self.configs.get("ocr.mock_text", "")
        text = str(configured.get(image_id, "") if isinstance(configured, dict) else configured)
        score = float(self.configs.get("ocr.mock_blur_score", 1.0))
        return OCRPayload(text=text, lines=[line for line in text.splitlines() if line.strip()], blur_score=score)


class LocalTesseractProvider:
    """Real local OCR. Tesseract execution and HEIC decoding require no external service."""

    def __init__(self, configs: ConfigService) -> None:
        self.language = str(configs.get("ocr.language", "eng"))
        self.psm = int(configs.get("ocr.tesseract_psm", 6))
        configured_timeout = float(configs.get("ocr.local_timeout_seconds", 10))
        self.timeout = min(max(configured_timeout, 0.1), 10.0)

    def _recognize_sync(self, content: bytes) -> OCRPayload:
        register_heif_opener()
        try:
            with Image.open(BytesIO(content)) as source:
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise AppError(
                "image cannot be decoded; for HEIC upload a standards-compliant HEIC file",
                code="IMAGE_DECODE_FAILED", status_code=422,
            ) from error
        grayscale = image.convert("L")
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_variance = float(ImageStat.Stat(edges).var[0])
        blur_score = min(1.0, edge_variance / 500.0)
        try:
            text = pytesseract.image_to_string(
                image, lang=self.language, config=f"--psm {self.psm}", timeout=self.timeout,
            )
        except RuntimeError as error:
            raise AppError("OCR service timed out; please retry", code="OCR_TIMEOUT", status_code=504) from error
        except pytesseract.TesseractNotFoundError as error:
            raise AppError("local OCR engine is unavailable", code="OCR_UNAVAILABLE", status_code=503) from error
        except pytesseract.TesseractError as error:
            logger.warning("local Tesseract failed with status %s", error.status)
            raise AppError("local OCR failed", code="OCR_UNAVAILABLE", status_code=503) from error
        return OCRPayload(text=text, lines=[line for line in text.splitlines() if line.strip()], blur_score=blur_score)

    async def recognize(self, content: bytes, mime_type: str, image_id: str) -> OCRPayload:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._recognize_sync, content), timeout=self.timeout)
        except TimeoutError as error:
            raise AppError("OCR service timed out; please retry", code="OCR_TIMEOUT", status_code=504) from error


class HttpOCRProvider:
    def __init__(self, configs: ConfigService) -> None:
        self.endpoint = str(configs.get("ocr.http.endpoint", "")).strip()
        self.api_key = str(configs.get("ocr.http.api_key", "")).strip()
        configured_timeout = float(configs.get("ocr.http.timeout_seconds", 10))
        self.timeout = min(max(configured_timeout, 0.1), 10.0)
        if not self.endpoint.startswith(("https://", "http://")):
            raise AppError("OCR provider is not configured", code="OCR_UNAVAILABLE", status_code=503)

    async def recognize(self, content: bytes, mime_type: str, image_id: str) -> OCRPayload:
        headers = {"Accept": "application/json", "X-Image-ID": image_id}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(
                    self.endpoint, content=content, headers={**headers, "Content-Type": mime_type}
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as error:
            raise AppError("OCR service timed out; please retry", code="OCR_TIMEOUT", status_code=504) from error
        except (httpx.HTTPError, ValueError, TypeError) as error:
            logger.warning("OCR provider request failed: %s", type(error).__name__)
            raise AppError("OCR service is temporarily unavailable", code="OCR_UNAVAILABLE", status_code=503) from error
        text = str(payload.get("text", ""))
        lines = payload.get("lines")
        if not isinstance(lines, list):
            lines = text.splitlines()
        return OCRPayload(
            text=text, lines=[str(line).strip() for line in lines if str(line).strip()],
            blur_score=float(payload.get("blur_score", 1.0)),
        )


def classify_image(text: str, threshold: float = 0.35) -> tuple[str, float]:
    lowered = text.casefold()
    rules = [
        ("exploded_diagram", ("item no", "exploded", "爆炸图", "序号")),
        ("engine_nameplate", ("engine model", "engine no", "发动机型号", "发动机号")),
        ("machine_nameplate", ("serial no", "machine model", "整机型号", "序列号", "制造日期")),
        ("package_label", ("barcode", "qty", "quantity", "包装", "条码")),
        ("old_part_number", ("part no", "part number", "p/n", "零件号", "配件编号", "oem")),
        ("part_photo", ("filter", "bearing", "pump", "滤芯", "轴承", "泵")),
    ]
    best_type, hits = "unknown", 0
    for image_type, words in rules:
        current = sum(word in lowered for word in words)
        if current > hits:
            best_type, hits = image_type, current
    confidence = min(0.98, 0.25 + hits * 0.25) if hits else 0.0
    return (best_type, confidence) if confidence >= threshold else ("unknown", confidence)


FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "machine_brand": (
        r"(?:brand|manufacturer|品牌|制造商)\s*[:：#-]?\s*([A-Za-z][A-Za-z0-9 ._-]{1,30})",
    ),
    "machine_model": (
        r"(?:machine\s*model|(?<!engine\s)model|整机型号|设备型号)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{1,39})",
    ),
    "serial_number": (
        r"(?:serial\s*(?:no|number)?|s/n|序列号|机身号)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{2,49})",
    ),
    "engine_model": (
        r"(?:engine\s*model|发动机型号)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{1,39})",
    ),
    "year": (
        r"(?:year|mfg\s*year|出厂年份|制造年份)\s*[:：#-]?\s*((?:19|20)\d{2})",
    ),
    "part_no": (
        r"(?:part\s*(?:no|number)|p/n|零件号|配件编号)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{2,49})",
    ),
    "oem_no": (
        r"(?:oem\s*(?:no|number)?|OEM编号)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{2,49})",
    ),
}


def extract_fields(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value: Any = match.group(1).strip(" .:-")
                result[field] = int(value) if field == "year" else value
                break
    return result


class ImageRecognitionService:
    def __init__(self, db: Session, owner_key: str) -> None:
        self.db = db
        self.owner_key = owner_key
        self.configs = ConfigService(db)

    def image(self, image_id: str) -> FileObject:
        record = self.db.get(FileObject, image_id)
        if record is None or record.owner_key != self.owner_key:
            raise AppError("image not found", code="IMAGE_NOT_FOUND", status_code=404)
        if record.mime_type not in {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}:
            raise AppError("file is not an image", code="INVALID_IMAGE", status_code=415)
        return record

    def provider(self) -> OCRProvider:
        name = str(self.configs.get("ocr.provider", "local_tesseract")).casefold()
        if name == "local_tesseract":
            return LocalTesseractProvider(self.configs)
        if name == "mock":
            return MockOCRProvider(self.configs)
        if name == "http":
            return HttpOCRProvider(self.configs)
        raise AppError("unknown OCR provider", code="OCR_UNAVAILABLE", status_code=503)

    async def ocr(self, image_id: str) -> OCRPayload:
        record = self.image(image_id)
        if record.ocr_text is not None:
            return OCRPayload(record.ocr_text, record.ocr_lines or [])
        content = StorageService(self.db).read(record)
        payload = await self.provider().recognize(content, record.mime_type, record.id)
        threshold = float(self.configs.get("ocr.blur_threshold", 0.25))
        if payload.blur_score < threshold:
            raise AppError("image is blurry; please upload a clearer image", code="IMAGE_BLURRY", status_code=422)
        payload.text = payload.text.strip()
        payload.lines = [line.strip() for line in payload.lines if line.strip()]
        if not payload.text:
            raise AppError("no text recognized; enter details manually", code="OCR_EMPTY", status_code=422)
        record.ocr_text, record.ocr_lines = payload.text, payload.lines
        self.db.commit()
        return payload

    async def parse(self, image_id: str) -> dict[str, Any]:
        record = self.image(image_id)
        payload = await self.ocr(image_id)
        threshold = float(self.configs.get("image.classification_threshold", 0.35))
        image_type, confidence = classify_image(payload.text, threshold)
        extracted = extract_fields(payload.text)
        record.image_type, record.extracted_info = image_type, extracted
        self.db.commit()
        return {
            "image_id": record.id, "raw_text": payload.text, "lines": payload.lines,
            "image_type": image_type, "confidence": confidence, "extracted_info": extracted,
        }

    async def match(self, image_ids: list[str], user_hint: str | None, session_id: str, lang: str = "en") -> dict[str, Any]:
        started = time.perf_counter()
        if len(set(image_ids)) != len(image_ids):
            raise AppError("duplicate image IDs are not allowed", code="INVALID_IMAGE_IDS", status_code=422)
        parsed = [await self.parse(image_id) for image_id in image_ids]
        combined_text = "\n".join([item["raw_text"] for item in parsed] + ([user_hint] if user_hint else []))
        extracted = extract_fields(combined_text)
        for item in parsed:
            extracted = {**item["extracted_info"], **extracted}

        search = PartSearchService(self.db, lang)
        results = []
        if extracted.get("part_no"):
            results.append(search.part_number(str(extracted["part_no"])))
        if extracted.get("oem_no"):
            results.append(search.oem(str(extracted["oem_no"])))
        if extracted.get("engine_model"):
            results.append(search.engine(str(extracted["engine_model"])))
        if extracted.get("machine_brand"):
            results.append(search.machine(str(extracted["machine_brand"]), extracted.get("machine_model")))

        minimum = float(self.configs.get("image.match_min_confidence", 0.0))
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for result in results:
            for candidate_model in result.candidates:
                candidate = candidate_model.model_dump(mode="json")
                part_id = candidate["part"]["id"]
                if part_id not in seen and candidate["confidence"] >= minimum:
                    candidates.append(candidate)
                    seen.add(part_id)
        candidates.sort(key=lambda item: (-item["confidence"], item["part"]["part_no"]))
        status = "multiple" if len(candidates) > 1 else "exact" if len(candidates) == 1 else "not_found"
        suggestions = []
        if not candidates:
            suggestions = (["已识别设备型号，请选择配件系统或补充零件号"]
                           if extracted.get("machine_model") else
                           ["请补充清晰的零件号/铭牌照片", "可转人工查询"])
        response = {
            "match_status": status, "extracted_info": extracted, "images": parsed,
            "candidates": candidates, "suggestions": suggestions,
        }
        log = PartQueryLog(
            session_id=session_id, query_type="image", query_text=user_hint,
            request_data={"image_ids": image_ids, "user_hint": user_hint}, raw_input={"image_ids": image_ids},
            extracted_info=extracted,
            ai_result={"provider": self.configs.get("ocr.provider", "local_tesseract"), "match_status": status},
            result_count=len(candidates), confidence=candidates[0]["confidence"] if candidates else 0,
            match_status=status, need_manual=status in {"multiple", "not_found"},
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        self.db.add(log)
        self.db.flush()
        for candidate in candidates:
            self.db.add(AiMatchEvidence(
                query_log_id=log.id, part_id=candidate["part"]["id"],
                confidence=candidate["confidence"], reason=candidate["reason"],
                evidence={"image_ids": image_ids, "matches": candidate.get("evidence", []), "normalized": [{
                    "type": "ocr", "content": "OCR 提取字段与数据库目录匹配",
                    "source_ref": f"image:{image_id}", "confidence": candidate["confidence"],
                } for image_id in image_ids]},
            ))
        self.db.commit()
        response["query_id"] = log.id
        return response
