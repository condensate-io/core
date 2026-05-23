from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str = "postgresql://condensate:password@localhost:5432/condensate_db"
    SQLALCHEMY_POOL_SIZE: int = 30
    SQLALCHEMY_MAX_OVERFLOW: int = 50
    SQLALCHEMY_POOL_TIMEOUT: int = 60
    SQLALCHEMY_POOL_RECYCLE: int = 1800

    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None

    # Paths & Security
    LOCALMEMCP_PATH: str = "/app/localmemcp_data"
    CONDENSATE_SECRET: str = "super-secret-key"
    REVIEW_MODE: str = "manual"
    APP_ROOT: str = "/app"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    UPLOAD_DIR: str = "uploads"

    # LLM config
    LLM_ENABLED: bool = False
    LLM_MODEL: str = "phi3"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MAX_CONCURRENCY: int = 4

    # Thresholds
    INSTRUCTION_BLOCK_THRESHOLD: float = 0.5
    SAFETY_BLOCK_THRESHOLD: float = 0.7
    CONFIDENCE_THRESHOLD: float = 0.8

    # Synapse Engine
    SYNAPSE_ENGINE_ENABLED: bool = True
    SYNAPSE_LEARNING_RATE: float = 0.08
    SYNAPSE_DECAY_RATE: float = 0.995
    SYNAPSE_PRUNE_THRESHOLD: float = 0.05
    SYNAPSE_CONSOLIDATION_THRESHOLD: float = 0.75

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def final_qdrant_url(self) -> str:
        if self.QDRANT_URL:
            return self.QDRANT_URL
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    def validate_startup(self) -> None:
        """Validate crucial startup settings to prevent failures at runtime."""
        if not (0.0 <= self.INSTRUCTION_BLOCK_THRESHOLD <= 1.0):
            raise ValueError(
                f"INSTRUCTION_BLOCK_THRESHOLD must be in [0.0, 1.0], got {self.INSTRUCTION_BLOCK_THRESHOLD}"
            )
        if not (0.0 <= self.SAFETY_BLOCK_THRESHOLD <= 1.0):
            raise ValueError(f"SAFETY_BLOCK_THRESHOLD must be in [0.0, 1.0], got {self.SAFETY_BLOCK_THRESHOLD}")
        if not (0.0 <= self.CONFIDENCE_THRESHOLD <= 1.0):
            raise ValueError(f"CONFIDENCE_THRESHOLD must be in [0.0, 1.0], got {self.CONFIDENCE_THRESHOLD}")
        if not (0.0 < self.SYNAPSE_LEARNING_RATE < 1.0):
            raise ValueError(f"SYNAPSE_LEARNING_RATE must be in (0.0, 1.0), got {self.SYNAPSE_LEARNING_RATE}")
        if not (0.0 < self.SYNAPSE_DECAY_RATE <= 1.0):
            raise ValueError(f"SYNAPSE_DECAY_RATE must be in (0.0, 1.0], got {self.SYNAPSE_DECAY_RATE}")
        if not (0.0 <= self.SYNAPSE_PRUNE_THRESHOLD <= 1.0):
            raise ValueError(f"SYNAPSE_PRUNE_THRESHOLD must be in [0.0, 1.0], got {self.SYNAPSE_PRUNE_THRESHOLD}")
        if not (0.0 <= self.SYNAPSE_CONSOLIDATION_THRESHOLD <= 1.0):
            raise ValueError(
                f"SYNAPSE_CONSOLIDATION_THRESHOLD must be in [0.0, 1.0], got {self.SYNAPSE_CONSOLIDATION_THRESHOLD}"
            )


# Singleton settings instance
settings = Settings()
