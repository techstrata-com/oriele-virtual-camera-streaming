from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cameras, health, live, videos
from app.config import get_settings
from app.db.init_db import init_db


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    app = FastAPI(title="Virtual Camera Platform", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(videos.router)
    app.include_router(cameras.router)
    app.include_router(live.router)

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    return app


app = create_app()

