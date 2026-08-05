from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success
from app.models import SysConfig

router = APIRouter(prefix="/api/v1/config", tags=["Public configuration"])

# Security boundary: adding a sys_config does not make it public. Every exposed
# key must be explicitly reviewed and added here; secret rows are always excluded.
PUBLIC_CONFIG_KEYS = (
    "frontend.api_base_url",
    "support.whatsapp_url",
    "support.zalo_url",
    "support.telegram_url",
    "support.wechat_label",
)


@router.get("/public")
def public_config(db: Annotated[Session, Depends(get_db)]) -> dict:
    data: dict[str, object] = {}
    for key in PUBLIC_CONFIG_KEYS:
        item = db.get(SysConfig, key)
        if item is not None and not item.is_secret:
            data[key] = item.value
    return success(data)
