from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    FILE_ALLOWED_TYPES: List[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int
    
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str
    POSTGRES_EXTRA_PARAMS: str


    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None

    GENERATION_MODEL_ID_LITERAL: Optional[List[str]] = None
    GENERATION_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_ID: Optional[str] = None
    EMBEDDING_MODEL_SIZE: Optional[int] = None

    INPUT_DAFAULT_MAX_CHARACTERS: Optional[int] = None
    GENERATION_DAFAULT_MAX_TOKENS: Optional[int] = None
    GENERATION_DAFAULT_TEMPERATURE: Optional[float] = None

    VECTOR_DB_BACKEND_LITERAL: Optional[List[str]] = None
    VECTOR_DB_BACKEND: str
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METHOD: str = None
    DEFAULT_LANG: str = "ar"
    PRIMARY_LANG: str = "en"
    DEFAULT_PROJECT_ID: int
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # -----------------------------
    # ✅ temperature validator
    # -----------------------------
    @field_validator("GENERATION_DAFAULT_TEMPERATURE", mode="before")
    def parse_temperature(cls, v):
        # empty or missing → None
        if v in (None, "", " ", "null", "None"):
            return None

        # try casting to float
        try:
            return float(v)
        except:
            return None


def get_settings():
    return Settings()
