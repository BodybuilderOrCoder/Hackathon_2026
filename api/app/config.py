from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str | None = None
    fleetmix_seed_xlsx: str | None = None
    worker_poll_seconds: float = 1.0
    optimizer_time_limit_seconds: int = 10

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = (PROJECT_ROOT / "data" / "fleetmix_erp.db").as_posix()
        return f"sqlite:///{db_path}"

    @property
    def seed_path(self) -> Path:
        if self.fleetmix_seed_xlsx:
            return Path(self.fleetmix_seed_xlsx).expanduser().resolve()
        return PROJECT_ROOT / "outputs" / "01a1cbad-1a1e-7de1-899b-92bedce65edf" / "FleetMix_ERP_Operational_Dataset.xlsx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
