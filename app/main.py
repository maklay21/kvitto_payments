from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.routes import router
from app.core.logging_config import configure_logging
from app.db.session import SessionLocal
from app.services import seed_tariffs


def create_app(session_factory: Callable[[], Session] = SessionLocal) -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with session_factory() as db:
            seed_tariffs(db)
        yield

    application = FastAPI(title="Kvitto Payments API", version="0.1.0", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
