"""Application settings sourced from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field("development", alias="APP_ENV")
    database_url: str = Field(
        "mysql+aiomysql://inky:inky@db:3306/inky_easel", alias="DATABASE_URL"
    )
    service_secret: str = Field("dev-service-secret", alias="SERVICE_SECRET")
    public_base_url: str = Field("http://localhost:8000", alias="PUBLIC_BASE_URL")
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")
    content_cache_minutes: int = Field(15, alias="CONTENT_CACHE_MINUTES")
    frame_firmware_dir: str = Field("/app/frame-firmware", alias="FRAME_FIRMWARE_DIR")
    firestore_mongodb_uri: str | None = Field(None, alias="FIRESTORE_MONGODB_URI")
    firestore_mongodb_database: str = Field("", alias="FIRESTORE_MONGODB_DATABASE")
    firmware_releases_collection: str = Field("firmware_releases", alias="FIRMWARE_RELEASES_COLLECTION")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
