import asyncio
import time
from collections import deque
from typing import Deque, Set

import httpx

from app.core.config import settings
from app.models.trade import Trade
from app.services.polymarket_data_api import fetch_trades


class TradeBuffer:
    """
    buf:
      - слева (index 0) — САМЫЕ свежие
      - справа (index -1) — самые старые
    Мы кладём новые сделки через appendleft().
    """
    def __init__(self) -> None:
        self.buf: Deque[Trade] = deque(maxlen=settings.buffer_max_size)
        self.seen: Set[str] = set()

    def push_many(self, trades: list[Trade], cutoff_ts: int) -> int:
        added = 0
        for t in trades:
            if t.timestamp < cutoff_ts:
                continue

            k = t.key()
            if k in self.seen:
                continue

            self.seen.add(k)
            self.buf.appendleft(t)  # свежие слева
            added += 1

        # защита от разрастания seen
        if len(self.seen) > settings.buffer_max_size * 2:
            self.seen = {x.key() for x in self.buf if x.key()}

        return added

    def prune_older_than(self, cutoff_ts: int) -> None:
        """
        Удаляем из буфера всё, что старше cutoff_ts.
        Т.к. старые справа — попаем справа.
        """
        while self.buf and self.buf[-1].timestamp < cutoff_ts:
            old = self.buf.pop()
            k = old.key()
            if k:
                self.seen.discard(k)

        # дополнительная страховка
        if len(self.seen) > settings.buffer_max_size * 2:
            self.seen = {x.key() for x in self.buf if x.key()}


async def run_ingestor(trade_buffer: TradeBuffer, stop_event: asyncio.Event) -> None:
    """
    Регулярно опрашивает Polymarket Data API и наполняет буфер свежими сделками.
    """
    backoff = 1.0

    async with httpx.AsyncClient(timeout=10.0) as client:
        while not stop_event.is_set():
            cutoff = int(time.time()) - settings.since_sec

            try:
                trades = await fetch_trades(client)
                trade_buffer.push_many(trades, cutoff_ts=cutoff)

                backoff = 1.0
                await asyncio.sleep(settings.poll_interval_sec)

            except Exception:
                # мягкий backoff, чтобы не "умереть" и не долбить API
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
