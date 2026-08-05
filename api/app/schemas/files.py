from pydantic import BaseModel


class FileUploadResult(BaseModel):
    file_id: str
    url: str
    mime_type: str
    size: int
