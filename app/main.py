from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router
from app.services.broadcaster import Broadcaster
from app.services.ingestor import TradeBuffer, run_ingestor
from app.services.scheduler import run_scheduler
import asyncio

def create_app() -> FastAPI:
    app = FastAPI(title="Polymarket Whale Backend")

    origins = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    app.state.trade_buffer = TradeBuffer()
    app.state.broadcaster = Broadcaster()
    app.state.stop_event = asyncio.Event()
    app.state.tasks = []

    @app.on_event("startup")
    async def on_startup():
        app.state.tasks = [
            asyncio.create_task(run_ingestor(app.state.trade_buffer, app.state.stop_event)),
            asyncio.create_task(run_scheduler(app.state.trade_buffer, app.state.broadcaster, app.state.stop_event)),
        ]

    @app.on_event("shutdown")
    async def on_shutdown():
        app.state.stop_event.set()
        for t in app.state.tasks:
            t.cancel()

    return app

app = create_app()
