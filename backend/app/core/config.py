
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "VyaparOS"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str
    DEMO_STORE_PHONE: str = "+910000000001"
    DEMO_OWNER_PHONE: str = "+910000000002"

    EVON_BASE_URL: str = ""
    EVON_API_KEY: str = ""
    EVON_MODEL: str = ""

    PRISMA_API_KEY: str = ""
    TIMBRE_API_KEY: str = ""

    JWT_SECRET: str

    GNANI_API_KEY: str = ""
    PRISMA_BASE_URL: str = "https://api.vachana.ai/stt/v3"
    PRISMA_MODEL: str = "prisma-v3.0"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
