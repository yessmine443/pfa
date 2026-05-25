import json
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "changeme"

    database_url: str = "postgresql+asyncpg://sparky:sparky_pass@localhost:5432/sparky_db"

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_bucket: str = "sparky-documents"

    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    mistral_vision_model: str = "pixtral-12b-2409"

    n8n_webhook_url: str = ""
    n8n_webhook_secret: str = "sparky-secret"

    allowed_origins: List[str] = ["http://localhost:4200"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
            return [s.strip() for s in stripped.split(",") if s.strip()]
        return v


settings = Settings()
