"""
Health/Readiness server — بررسی واقعی process، DB، scheduler و queue.
صرف اتصال DB سلامت scheduler را اثبات نمی‌کند.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

from config.settings import get_settings
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def _check_db() -> dict[str, Any]:
    try:
        from src.infrastructure.db.session import get_session
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:100]}


async def _check_scheduler() -> dict[str, Any]:
    try:
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.models import SchedulerHeartbeatModel
        from sqlalchemy import select
        async with get_session() as session:
            result = await session.execute(
                select(SchedulerHeartbeatModel)
                .order_by(SchedulerHeartbeatModel.beat_at.desc())
                .limit(1)
            )
            last = result.scalar_one_or_none()
        if not last:
            return {"status": "no_heartbeat"}
        age = (datetime.utcnow() - last.beat_at).total_seconds()
        threshold = get_settings().SCHEDULER_STALE_THRESHOLD
        if age > threshold:
            return {"status": "stale", "age_seconds": int(age)}
        return {"status": "ok", "age_seconds": int(age)}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:100]}


async def get_health() -> dict[str, Any]:
    db = await _check_db()
    scheduler = await _check_scheduler()
    overall = "ok" if db["status"] == "ok" else "degraded"
    if scheduler["status"] not in ("ok",):
        overall = "degraded"
    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "db": db,
            "scheduler": scheduler,
        },
    }


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(get_health())
        loop.close()
        body = json.dumps(data, ensure_ascii=False).encode()
        status = 200 if data["status"] == "ok" else 503
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress default HTTP logs


def start_health_server() -> None:
    settings = get_settings()
    server = HTTPServer(("0.0.0.0", settings.HEALTH_PORT), HealthHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info("health_server_started", port=settings.HEALTH_PORT)


def main() -> None:
    from src.infrastructure.logging.logger import setup_logging
    setup_logging()
    start_health_server()
    logger.info("health_server_running")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
