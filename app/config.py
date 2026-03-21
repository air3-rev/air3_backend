from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    app_name: str = "Simple Python API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Database Settings
    database_url: Optional[str] = "sqlite:///./app.db"
    journals_database_url: Optional[str] = "sqlite:///./journals.db"

    # Supabase Settings
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_db_pwd: Optional[str] = None

    # Trusted Hosts
    trusted_hosts: List[str] = ["localhost", "127.0.0.1", "testserver"]

    # CORS Settings
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]

    # LENS API SETTINGS
    lens_url: Optional[str] = None
    lens_token: Optional[str] = None

    # OPEN AI SETTINGS
    openai_api_key: Optional[str] = None

    # AI Model Configuration
    extraction_model: str = "gpt-4o-mini"
    review_model: str = "gpt-4o"
    full_text_extraction_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    scope_generation_model: str = "gpt-4o-mini"

    @model_validator(mode='after')
    def check_required_secrets(self) -> 'Settings':
        required = {
            'supabase_url': self.supabase_url,
            'supabase_jwt_secret': self.supabase_jwt_secret,
            'openai_api_key': self.openai_api_key,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required env vars: {missing}")
        return self

    class Config:
        env_file = [".env.local", ".env"]
        case_sensitive = False


settings = Settings()
