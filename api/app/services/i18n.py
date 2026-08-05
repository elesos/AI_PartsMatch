from __future__ import annotations

import ipaddress
from copy import deepcopy
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LanguagePreference
from app.services.config_service import ConfigService

SUPPORTED_LANGUAGES = ("zh", "en", "vi")
LANGUAGE_LABELS = {"zh": "中文", "en": "English", "vi": "Tiếng Việt"}

DEFAULT_MESSAGES: dict[str, dict[str, str]] = {
    "zh": {
        "common.ok": "成功", "error.not_found": "未找到匹配的配件",
        "error.invalid_request": "请求参数无效", "search.placeholder": "输入配件编号、OEM 编号或配件名称",
        "search.no_results": "暂无结果，请尝试其他关键词", "search.manual_help": "仍未找到？提交人工询价",
        "batch.upload": "上传 Excel 批量匹配", "batch.download_template": "下载模板",
    },
    "en": {
        "common.ok": "Success", "error.not_found": "No matching part was found",
        "error.invalid_request": "Invalid request", "search.placeholder": "Enter a part number, OEM number, or part name",
        "search.no_results": "No results. Try another keyword", "search.manual_help": "Still no match? Submit a manual inquiry",
        "batch.upload": "Upload Excel for batch matching", "batch.download_template": "Download template",
    },
    "vi": {
        "common.ok": "Thành công", "error.not_found": "Không tìm thấy phụ tùng phù hợp",
        "error.invalid_request": "Yêu cầu không hợp lệ", "search.placeholder": "Nhập mã phụ tùng, mã OEM hoặc tên phụ tùng",
        "search.no_results": "Không có kết quả. Hãy thử từ khóa khác", "search.manual_help": "Vẫn chưa tìm thấy? Gửi yêu cầu hỗ trợ",
        "batch.upload": "Tải Excel để đối chiếu hàng loạt", "batch.download_template": "Tải mẫu",
    },
}


def normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    code = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return code if code in SUPPORTED_LANGUAGES else None


def localized_name(part: Any, lang: str) -> str:
    # name_cn in the product documents is the existing name_zh database column.
    order = list(dict.fromkeys((lang, "en", "zh")))
    for code in order:
        value = getattr(part, f"name_{code}", None)
        if value and value.strip():
            return value
    return ""


def messages(db: Session, lang: str) -> dict[str, str]:
    result = deepcopy(DEFAULT_MESSAGES[lang])
    configured = ConfigService(db).get("i18n.messages", {})
    if isinstance(configured, dict) and isinstance(configured.get(lang), dict):
        result.update({str(key): str(value) for key, value in configured[lang].items()})
    return result


def _accept_language(value: str | None) -> str | None:
    choices: list[tuple[float, int, str]] = []
    for index, item in enumerate((value or "").split(",")):
        token, *parameters = item.strip().split(";")
        lang = normalize_language(token)
        if not lang:
            continue
        quality = 1.0
        for parameter in parameters:
            if parameter.strip().startswith("q="):
                try:
                    quality = float(parameter.strip()[2:])
                except ValueError:
                    quality = 0
        choices.append((quality, -index, lang))
    return max(choices)[2] if choices else None


def _trusted_peer(peer: str, configured: Any) -> bool:
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for value in configured if isinstance(configured, list) else []:
        try:
            if address in ipaddress.ip_network(str(value), strict=False):
                return True
        except ValueError:
            continue
    return False


def _country_language(request: Request, config: ConfigService) -> str | None:
    peer = request.client.host if request.client else ""
    trusted = config.get("i18n.trusted_proxy_ips", [])
    if not _trusted_peer(peer, trusted):
        return None
    header_name = str(config.get("i18n.country_header", "CF-IPCountry"))
    country = request.headers.get(header_name, "").strip().upper()
    if country == "CN":
        return "zh"
    if country == "VN":
        return "vi"
    return "en" if len(country) == 2 and country.isalpha() else None


def request_owner_key(request: Request) -> str | None:
    session_id = request.headers.get("X-Session-Id")
    # Match the anonymous-owner grammar without importing the cart router.
    if session_id and 8 <= len(session_id) <= 100 and session_id[0].isalnum() and all(
        char.isalnum() or char in "._:-" for char in session_id
    ):
        return f"session:{session_id}"
    return None


def resolve_language(request: Request, db: Session, explicit: str | None = None) -> str:
    """Priority: explicit query/body > owner DB preference > cookie > trusted country > Accept-Language > en."""
    selected = normalize_language(explicit)
    if selected:
        return selected
    owner_key = request_owner_key(request)
    if owner_key:
        preference = db.scalar(select(LanguagePreference).where(LanguagePreference.owner_key == owner_key))
        if preference:
            return preference.language
    config = ConfigService(db)
    cookie_name = str(config.get("i18n.cookie_name", "partsmatch_lang"))
    selected = normalize_language(request.cookies.get(cookie_name))
    if selected:
        return selected
    return _country_language(request, config) or _accept_language(request.headers.get("Accept-Language")) or "en"
