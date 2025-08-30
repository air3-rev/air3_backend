from typing import List, Optional

from pydantic import Field
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

    # Supabase Settings
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_service_role_key: Optional[str] = None

    # CORS Settings
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]

    # LENS API SETTINGS
    LENS_URL: str = Field(..., alias="LENS_URL")
    LENS_TOKEN: str = Field(..., alias="LENS_TOKEN")

    OPENAI_API_KEY: str = Field(..., alias="OPENAI_API_KEY")

    SUPABASE_SERVICE_ROLE_KEY: str = Field(..., alias="OPENAI_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
