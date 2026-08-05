from io import BytesIO

import pytest
from fastapi import UploadFile

from app.core.exceptions import AppError
from app.services.storage import IMAGE_LIMIT, StorageService


@pytest.mark.asyncio
async def test_rejects_unsupported_extension() -> None:
    service = object.__new__(StorageService)
    with pytest.raises(AppError) as error:
        await service.upload(UploadFile(filename="payload.exe", file=BytesIO(b"bad")))
    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_rejects_oversized_image_before_storage() -> None:
    service = object.__new__(StorageService)
    with pytest.raises(AppError) as error:
        await service.upload(UploadFile(filename="large.jpg", file=BytesIO(b"x" * (IMAGE_LIMIT + 1))))
    assert error.value.status_code == 413
