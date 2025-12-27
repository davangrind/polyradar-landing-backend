import httpx
from typing import List
from app.core.config import settings
from app.models.trade import Trade

def _build_params() -> dict:
    params = {
        "limit": str(settings.limit),
        "offset": "0",
        "takerOnly": "true" if settings.taker_only else "false",
        # CASH фильтр: filterType + filterAmount должны идти вместе :contentReference[oaicite:6]{index=6}
        "filterType": "CASH",
        "filterAmount": str(settings.min_usd),
    }
    return params

async def fetch_trades(client: httpx.AsyncClient) -> List[Trade]:
    r = await client.get(str(settings.polymarket_trades_url), params=_build_params(), headers={"accept":"application/json"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return []
    out: List[Trade] = []
    for item in data:
        try:
            out.append(Trade.model_validate(item))
        except Exception:
            continue
    return out
