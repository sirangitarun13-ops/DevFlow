"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_jwt_secret_key_missing_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="")
    errors = exc_info.value.errors()
    assert any("JWT_SECRET_KEY must be configured" in str(e["msg"]) for e in errors)


def test_jwt_secret_key_empty_string_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="")
    errors = exc_info.value.errors()
    assert any("JWT_SECRET_KEY must be configured" in str(e["msg"]) for e in errors)


def test_jwt_secret_key_too_short_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="short")
    errors = exc_info.value.errors()
    assert any("at least 32 characters" in str(e["msg"]) for e in errors)


def test_jwt_secret_key_valid_length_accepted() -> None:
    valid_secret = "a" * 32
    settings_obj = Settings(jwt_secret_key=valid_secret)
    assert settings_obj.jwt_secret_key == valid_secret


def test_jwt_secret_key_longer_than_minimum_accepted() -> None:
    valid_secret = "a" * 64
    settings_obj = Settings(jwt_secret_key=valid_secret)
    assert settings_obj.jwt_secret_key == valid_secret