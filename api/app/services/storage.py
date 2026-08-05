from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import boto3
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import FileObject
from app.services.config_service import ConfigService

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
EXCEL_EXTENSIONS = {".xlsx", ".xls"}
IMAGE_LIMIT = 10 * 1024 * 1024
EXCEL_LIMIT = 5 * 1024 * 1024
IMAGE_MIMES = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"},
    ".webp": {"image/webp"}, ".heic": {"image/heic", "image/heif"},
}


def detect_image_type(content: bytes) -> tuple[str, str] | None:
    """Return canonical extension/MIME from bytes; client metadata is not trusted."""
    if len(content) >= 3 and content[:3] == b"\xff\xd8\xff":
        return ".jpg", "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in {
        b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1",
    }:
        return ".heic", "image/heic"
    return None


class StorageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        settings = get_settings()
        configs = ConfigService(db)
        self.bucket = configs.get("storage.bucket", settings.s3_bucket)
        self.public_url = configs.get("storage.public_url", settings.s3_public_url).rstrip("/")
        self.client = boto3.client(
            "s3", endpoint_url=configs.get("storage.endpoint_url", settings.s3_endpoint_url),
            aws_access_key_id=configs.get("storage.access_key", settings.s3_access_key),
            aws_secret_access_key=configs.get("storage.secret_key", settings.s3_secret_key),
            region_name="us-east-1",
        )

    async def upload(self, upload: UploadFile, *, owner_key: str | None = None, images_only: bool = False) -> FileObject:
        name = Path(upload.filename or "upload").name
        extension = Path(name).suffix.lower()
        if extension in IMAGE_EXTENSIONS:
            limit = IMAGE_LIMIT
        elif extension in EXCEL_EXTENSIONS and not images_only:
            limit = EXCEL_LIMIT
        else:
            raise AppError("unsupported file type", code=40001, status_code=415)
        content = await upload.read(limit + 1)
        if len(content) > limit:
            raise AppError("file is too large", code=40002, status_code=413)
        mime_type = upload.content_type or "application/octet-stream"
        if extension in IMAGE_EXTENSIONS:
            detected = detect_image_type(content)
            if detected is None:
                raise AppError("file content is not a supported image", code="INVALID_IMAGE", status_code=415)
            detected_extension, detected_mime = detected
            extension_matches = (
                detected_extension == ".jpg" and extension in {".jpg", ".jpeg"}
            ) or detected_extension == extension
            if mime_type not in IMAGE_MIMES[extension] or not extension_matches:
                raise AppError("image extension, MIME and content do not match", code="INVALID_IMAGE", status_code=415)
            mime_type = detected_mime
        file_id = str(uuid4())
        object_key = f"uploads/{datetime.now(UTC):%Y/%m/%d}/{file_id}{extension}"
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=content, ContentType=mime_type)
        record = FileObject(
            id=file_id, object_key=object_key, original_name=name, mime_type=mime_type,
            size=len(content), url=f"{self.public_url}/{object_key}", owner_key=owner_key,
            created_at=datetime.now(UTC),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def read(self, record: FileObject) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=record.object_key)["Body"].read()

    def delete(self, file_id: str) -> None:
        """Remove an owned upload after its domain reference has been deleted."""
        record = self.db.get(FileObject, file_id)
        if record is None:
            return
        self.client.delete_object(Bucket=self.bucket, Key=record.object_key)
        self.db.delete(record)
        self.db.commit()
