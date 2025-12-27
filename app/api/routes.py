from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio, time

router = APIRouter()

def get_state(request: Request):
    return request.app.state

@router.get("/health")
async def health():
    return {"ok": True, "ts": int(time.time())}

@router.get("/sse")
async def sse(request: Request):
    broadcaster = get_state(request).broadcaster
    q: asyncio.Queue[str] = await broadcaster.register()

    async def gen():
        try:
            # приветственный ping
            yield "event: hello\ndata: {\"ok\":true}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                msg = await q.get()
                yield msg
        finally:
            await broadcaster.unregister(q)

    return StreamingResponse(gen(), media_type="text/event-stream")

@router.get("/next")
async def next_trade(request: Request):
    # удобный endpoint для тестов/polling
    trade_buffer = get_state(request).trade_buffer
    if not trade_buffer.buf:
        return JSONResponse({"trade": None})
    t = trade_buffer.buf.pop()
    return JSONResponse({"trade": t.model_dump()})
