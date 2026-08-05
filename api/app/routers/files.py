from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import ApiResponse, success
from app.models import FileObject
from app.schemas.files import FileUploadResult
from app.services.storage import StorageService

router = APIRouter(prefix="/api/v1/files", tags=["Files"])


@router.get("/content/{object_key:path}", summary="Serve a public uploaded object over the API HTTPS origin")
def file_content(object_key: str, db: Session = Depends(get_db)) -> Response:
    if not object_key.startswith("uploads/") or ".." in object_key.split("/"):
        raise AppError("file not found", code=40401, status_code=404)
    record = db.query(FileObject).filter(FileObject.object_key == object_key).one_or_none()
    if record is None:
        raise AppError("file not found", code=40401, status_code=404)
    return Response(
        content=StorageService(db).read(record), media_type=record.mime_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/upload", response_model=ApiResponse[FileUploadResult], summary="Upload an image or Excel file")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    result = await StorageService(db).upload(file)
    return success(
        FileUploadResult(
            file_id=result.id,
            url=result.url,
            mime_type=result.mime_type,
            size=result.size,
        ).model_dump()
    )
