from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import ApiResponse, success
from app.schemas.images import ImageMatchRequest, ImageUploadResult, OCRResult, ParsedImageResult
from app.services.image_ocr import ImageRecognitionService
from app.services.storage import StorageService

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


def image_owner(x_session_id: Annotated[str | None, Header()] = None) -> str:
    if not x_session_id or len(x_session_id) > 100:
        raise AppError("X-Session-ID is required", code="SESSION_REQUIRED", status_code=400)
    return f"session:{x_session_id}"


@router.post("/upload", response_model=ApiResponse[ImageUploadResult])
async def upload_images(
    files: Annotated[list[UploadFile], File(min_length=1, max_length=5)],
    owner_key: str = Depends(image_owner), db: Session = Depends(get_db),
) -> dict:
    if len(files) > 5:
        raise AppError("at most 5 images are allowed", code="TOO_MANY_IMAGES", status_code=400)
    service = StorageService(db)
    records = [await service.upload(file, owner_key=owner_key, images_only=True) for file in files]
    return success({"images": [
        {"image_id": item.id, "url": item.url, "mime_type": item.mime_type, "size": item.size}
        for item in records
    ]})


@router.post("/{image_id}/ocr", response_model=ApiResponse[OCRResult])
async def recognize_image(
    image_id: str, owner_key: str = Depends(image_owner), db: Session = Depends(get_db),
) -> dict:
    payload = await ImageRecognitionService(db, owner_key).ocr(image_id)
    return success({"image_id": image_id, "raw_text": payload.text, "lines": payload.lines})


@router.post("/{image_id}/parse", response_model=ApiResponse[ParsedImageResult])
async def parse_image(
    image_id: str, owner_key: str = Depends(image_owner), db: Session = Depends(get_db),
) -> dict:
    return success(await ImageRecognitionService(db, owner_key).parse(image_id))


@router.post("/match")
async def match_images(
    request: ImageMatchRequest, owner_key: str = Depends(image_owner), db: Session = Depends(get_db),
) -> dict:
    return success(await ImageRecognitionService(db, owner_key).match(
        request.image_ids, request.user_hint, owner_key.removeprefix("session:"), request.lang
    ))
