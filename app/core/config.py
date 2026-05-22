from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Compliance Workflow System"
    API_V1_STR: str = "/api/v1"
    
    # Needs to be set in environment variables or .env file
    DATABASE_URL: str
    GEMINI_API_KEY: str
    UPLOADS_DIR: str = "uploads"
   

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
