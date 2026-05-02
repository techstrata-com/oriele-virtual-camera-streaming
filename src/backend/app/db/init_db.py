from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.session import engine
from app.models.base import Base


logger = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # SQLite doesn't auto-add new columns to existing tables when using create_all().
    # Since we don't use Alembic in this project, do a tiny SQLite-only migration.
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        existing_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(cameras)")).fetchall()
        }

        # New streaming columns (older DBs may also still have unused HLS columns; that's OK).
        if "rtsp_pid" not in existing_cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN rtsp_pid INTEGER"))
            logger.info("SQLite migration: added cameras.rtsp_pid")

        if "rtsp_url" not in existing_cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN rtsp_url VARCHAR"))
            logger.info("SQLite migration: added cameras.rtsp_url")

        if "http_live_url" not in existing_cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN http_live_url VARCHAR"))
            logger.info("SQLite migration: added cameras.http_live_url")

        if "client_id" not in existing_cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN client_id VARCHAR DEFAULT 'legacy'"))
            logger.info("SQLite migration: added cameras.client_id")

        if "device_label" not in existing_cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN device_label VARCHAR"))
            logger.info("SQLite migration: added cameras.device_label")

        conn.execute(
            text(
                "UPDATE cameras SET client_id = 'legacy' "
                "WHERE client_id IS NULL OR trim(client_id) = ''"
            )
        )

