from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Polymarket Data API trades endpoint
    polymarket_trades_url: AnyHttpUrl = Field(default="https://data-api.polymarket.com/trades")

    # фильтры “киты”
    min_usd: float = 100.0
    taker_only: bool = True

    # поллинг (как часто забираем новые сделки)
    poll_interval_sec: float = 7.5
    since_sec: int = 180
    limit: int = 5000

    # выдача на фронт (раз в 3-5 секунд)
    emit_interval_min_sec: float = 3.0
    emit_interval_max_sec: float = 5.0

    # дедуп / анти-”одна и та же сделка”
    recent_sent_size: int = 400
    buffer_max_size: int = 4000

    # CORS (поставишь домен фронта)
    cors_origins: str = "*"  # или "https://your-landing.com,https://www.your-landing.com"

settings = Settings()