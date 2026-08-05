import logging

import app.services.catalog_validation  # noqa: F401 - installs database invariant listeners

from fastapi import FastAPI
from app.core.config import get_settings
from app.core.cors import DatabaseCORSMiddleware
from app.core.exceptions import install_exception_handlers
from app.core.middleware import install_request_middleware
from app.routers.health import router as health_router
from app.routers.files import router as files_router
from app.routers.admin import router as admin_router
from app.routers.admin_crud import router as admin_crud_router
from app.routers.search import router as search_router
from app.routers.cart import router as cart_router
from app.routers.images import router as images_router
from app.routers.tickets import router as tickets_router, admin_router as admin_tickets_router
from app.routers.batch import router as batch_router
from app.routers.ai_admin import router as ai_admin_router
from app.routers.i18n import router as i18n_router
from app.routers.public_config import router as public_config_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="PartsMatch REST API. Every JSON endpoint uses the `{code, message, data}` envelope.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    install_request_middleware(application)
    application.add_middleware(DatabaseCORSMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(files_router)
    application.include_router(admin_router)
    application.include_router(admin_crud_router)
    application.include_router(search_router)
    application.include_router(cart_router)
    application.include_router(images_router)
    application.include_router(tickets_router)
    application.include_router(admin_tickets_router)
    application.include_router(batch_router)
    application.include_router(ai_admin_router)
    application.include_router(i18n_router)
    application.include_router(public_config_router)
    return application


app = create_app()
