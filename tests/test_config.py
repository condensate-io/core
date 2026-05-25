import pytest
from src.config import Settings

def test_settings_default_precedence():
    settings = Settings()
    # Check default or environment-injected values
    assert settings.DATABASE_URL in (
        "postgresql://condensate:password@localhost:5432/condensate_db",
        "postgresql://user:password@condensate-db:5432/condensate"
    )
    assert settings.ADMIN_USERNAME == "admin"
    assert settings.final_qdrant_url in ("http://localhost:6333", "http://condensate-vector:6333")

def test_settings_validation_errors():
    with pytest.raises(ValueError):
        invalid_settings = Settings(INSTRUCTION_BLOCK_THRESHOLD=1.5)
        invalid_settings.validate_startup()

    with pytest.raises(ValueError):
        invalid_settings = Settings(SAFETY_BLOCK_THRESHOLD=-0.5)
        invalid_settings.validate_startup()

    with pytest.raises(ValueError):
        invalid_settings = Settings(CONFIDENCE_THRESHOLD=1.2)
        invalid_settings.validate_startup()

    with pytest.raises(ValueError):
        invalid_settings = Settings(SYNAPSE_LEARNING_RATE=1.5)
        invalid_settings.validate_startup()

def test_settings_validation_success():
    valid_settings = Settings(
        INSTRUCTION_BLOCK_THRESHOLD=0.2,
        SAFETY_BLOCK_THRESHOLD=0.8,
        CONFIDENCE_THRESHOLD=0.9,
        SYNAPSE_LEARNING_RATE=0.1
    )
    # Should not raise any exception
    valid_settings.validate_startup()


def test_config_cache_ttl_default():
    settings = Settings()
    assert settings.CONFIG_CACHE_TTL_SECONDS == 30
