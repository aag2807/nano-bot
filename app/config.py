import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (SQLite by default for easy setup)
    database_url: str = "sqlite:///./nano_banking.db"
    
    # HuggingFace
    hf_model_name: str = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
    hf_token: Optional[str] = None
    
    # Security
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Storage
    customer_files_path: str = "./customer_files"
    max_file_size_mb: int = 10
    
    # API Settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # Banking Configuration
    bank_name: str = "Bank Of AI"
    verify_identity_required: bool = True
    max_login_attempts: int = 3
    session_timeout_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Ensure customer files directory exists
os.makedirs(settings.customer_files_path, exist_ok=True)