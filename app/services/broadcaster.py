import asyncio
from typing import Set

class Broadcaster:
    def __init__(self) -> None:
        self._clients: Set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def register(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._clients.add(q)
        return q

    async def unregister(self, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._clients.discard(q)

    async def broadcast(self, payload: str) -> None:
        async with self._lock:
            clients = list(self._clients)

        # не даём одному медленному клиенту стопорить остальных
        for q in clients:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # дропаем событие для этого клиента
                pass
