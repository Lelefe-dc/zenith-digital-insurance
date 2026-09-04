from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Zenith Digital Insurance Assistant"
    environment: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'zenith.db'}"
    admin_token: str = "change-me"
    max_upload_mb: int = 8
    upload_dir: str = str(BASE_DIR / "data" / "uploads")

    # Meta WhatsApp Cloud API settings. Leave blank for browser/demo mode.
    whatsapp_verify_token: str = "zenith-verify-token"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v23.0"

    # Policy security posture. Enable when an OTP provider is connected.
    require_policy_otp: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    Path(s.upload_dir).mkdir(parents=True, exist_ok=True)
    return s
