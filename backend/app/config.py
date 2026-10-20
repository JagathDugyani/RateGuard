from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    min_rate: float = 5
    max_rate: float = 100
    initial_rate: float = 50
    bucket_capacity: int = 50
    refill_rate: float = 50
    queue_capacity: int = 50
    leak_rate: float = 20
    telemetry_interval: float = 1
    cooldown_seconds: float = 3
    backend_url: str = "http://127.0.0.1:8000"
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
