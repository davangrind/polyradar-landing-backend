import asyncio
import json
import random
import time
import heapq
from collections import deque
from typing import Optional

from app.core.config import settings
from app.services.broadcaster import Broadcaster
from app.services.ingestor import TradeBuffer


def _usd_notional(trade) -> float:
    try:
        v = float(trade.price) * float(trade.size)
        return v if v > 0 else 0.0
    except Exception:
        return 0.0


def _sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _choose_from_top_k(
    candidates: list[tuple[float, int, int]],  # (usd, ts, idx)
    mode: str = "mix",
) -> Optional[int]:
    """
    Возвращает idx выбранного кандидата.
    mode:
      - "uniform": равновероятно из topK
      - "weighted": с весом в пользу больших (но не всегда top1)
      - "mix": 50% weighted, 50% uniform (рекомендуется)
    """
    if not candidates:
        return None

    if mode == "uniform":
        return random.choice(candidates)[2]

    if mode == "weighted":
        # лёгкая нелинейность: большие чаще, но не гарантированно
        # чтобы не было "всегда самый жирный"
        weights = [(usd ** 0.65) + 1e-6 for (usd, _ts, _idx) in candidates]
        return random.choices(candidates, weights=weights, k=1)[0][2]

    # mix
    if random.random() < 0.5:
        return random.choice(candidates)[2]
    weights = [(usd ** 0.65) + 1e-6 for (usd, _ts, _idx) in candidates]
    return random.choices(candidates, weights=weights, k=1)[0][2]


async def run_scheduler(trade_buffer: TradeBuffer, broadcaster: Broadcaster, stop_event: asyncio.Event) -> None:
    """
    Каждые 3–5 секунд отправляет всем клиентам одну сделку.

    Новая логика выдачи:
      - берём свежие сделки (timestamp >= now - since_sec)
      - фильтруем те, что недавно отправлялись (recent_sent)
      - находим TOP_K (по usd = price * size)
      - выбираем одну случайно из topK (uniform/weighted/mix)
      - если свежих нет — подмешиваем дубли из history_sent (тоже с анти-повтором)
    """
    recent_sent = deque(maxlen=settings.recent_sent_size)  # ключи недавно отправленных
    history_sent = deque(maxlen=1500)                      # отправленные сделки для fallback

    TOP_K = 10
    SCAN_LIMIT = 3500   # сколько максимум сделок в буфере сканируем за тик (защита по CPU)
    PICK_MODE = "mix"   # "uniform" | "weighted" | "mix"

    while not stop_event.is_set():
        now = int(time.time())
        cutoff = now - settings.since_sec  # у тебя сейчас 180

        # держим буфер свежим
        trade_buffer.prune_older_than(cutoff)

        trade = None

        if trade_buffer.buf:
            arr = list(trade_buffer.buf)
            n = min(len(arr), SCAN_LIMIT)

            # собираем кандидатов (usd, ts, idx) только свежие и не в recent_sent
            # затем берём nlargest(TOP_K)
            cand_list: list[tuple[float, int, int]] = []
            for i in range(n):
                cand = arr[i]
                if cand.timestamp < cutoff:
                    continue
                k = cand.key()
                if k and k in recent_sent:
                    continue
                usd = _usd_notional(cand)
                if usd <= 0:
                    continue
                cand_list.append((usd, int(cand.timestamp), i))

            # topK по usd (а при равенстве — по timestamp)
            if cand_list:
                top = heapq.nlargest(TOP_K, cand_list, key=lambda x: (x[0], x[1]))
                chosen_idx = _choose_from_top_k(top, mode=PICK_MODE)

                if chosen_idx is not None:
                    trade = arr[chosen_idx]

                    # удаляем выбранную из буфера, чтобы не повторялась мгновенно
                    arr.pop(chosen_idx)
                    trade_buffer.buf = deque(arr, maxlen=settings.buffer_max_size)

                    k = trade.key()
                    if k:
                        recent_sent.append(k)
                    history_sent.append(trade)

        # fallback: если свежих нет — берём из истории (дубликаты), но не совсем недавние
        if trade is None and history_sent:
            # попробуем найти что-то, чего не было совсем недавно
            for _ in range(40):
                cand = random.choice(list(history_sent))
                k = cand.key()
                if k and k in recent_sent:
                    continue
                trade = cand
                if k:
                    recent_sent.append(k)
                break

        # отправка
        if trade is None:
            hb = {"type": "heartbeat", "ts": now}
            await broadcaster.broadcast(_sse_event("heartbeat", json.dumps(hb)))
        else:
            await broadcaster.broadcast(_sse_event("trade", trade.model_dump_json()))

        delay = random.uniform(settings.emit_interval_min_sec, settings.emit_interval_max_sec)
        await asyncio.sleep(delay)
