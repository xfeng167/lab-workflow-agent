from typing import Literal
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppError(Exception):
    """A safe, application-owned error message; never raw provider text."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOONSHOT_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    api_key: SecretStr = Field(repr=False)
    base_url: Literal["https://api.moonshot.ai/v1"] = "https://api.moonshot.ai/v1"
    model: str = Field(default="kimi-k2.6", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    max_completion_tokens: int = Field(default=300, ge=1, le=300)
    thinking: Literal["disabled", "enabled", "omit"] = "disabled"

    @field_validator("api_key")
    @classmethod
    def nonempty_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("API key is required")
        return value


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        fields = sorted({str(e["loc"][0]) for e in exc.errors(include_input=False)})
        raise AppError("Invalid or missing Moonshot configuration: " + ", ".join(fields)) from None
    except (ValueError, OSError):
        raise AppError("Unable to load Moonshot configuration.") from None


class SourceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LAB_STORAGE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    api_url: Literal["http://127.0.0.1:8000"] = "http://127.0.0.1:8000"
    bearer_token: SecretStr = Field(default=SecretStr(""), repr=False)
    timeout_seconds: float = Field(default=10, gt=0, le=60, allow_inf_nan=False)

    @property
    def token_present(self) -> bool:
        return bool(self.bearer_token.get_secret_value().strip())


def load_source_settings(*, require_token: bool = False) -> SourceSettings:
    try:
        settings = SourceSettings()
    except ValidationError as exc:
        fields = sorted({str(e["loc"][0]) for e in exc.errors(include_input=False)})
        raise AppError("Invalid Lab Storage configuration: " + ", ".join(fields)) from None
    except (ValueError, OSError):
        raise AppError("Unable to load Lab Storage configuration.") from None
    if require_token and not settings.token_present:
        raise AppError("Lab Storage bearer token is required.")
    return settings
