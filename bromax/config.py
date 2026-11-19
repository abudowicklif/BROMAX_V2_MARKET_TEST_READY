from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROMAX_", env_file=".env", extra="ignore")
    host: str = "0.0.0.0"
    port: int = Field(default=8765, ge=1024, le=65535)
    symbol: str = "1HZ100V"
    history_count: int = Field(default=5000, ge=100, le=20000)
    max_ticks: int = Field(default=20000, ge=2000, le=100000)
    db_path: str = "data/bromax.sqlite3"
    deriv_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public"
    reconnect_max_seconds: int = Field(default=30, ge=2, le=120)
    min_sample: int = Field(default=1000, ge=100, le=20000)
    min_edge: float = Field(default=0.015, ge=0, le=0.5)
    max_feed_age_seconds: int = Field(default=10, ge=1, le=300)
    auto_start: bool = False

    @field_validator("symbol")
    @classmethod
    def valid_symbol(cls, value):
        if not value or not value.replace("_", "").isalnum() or len(value) > 30:
            raise ValueError("Symbol must be a valid Deriv symbol code")
        return value

settings = Settings()
