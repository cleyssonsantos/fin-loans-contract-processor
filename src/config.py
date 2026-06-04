from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str  # required

    # Database
    database_url: str  # required

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group_id: str = "loans-consumer-group"

    # Auth
    jwt_private_key_path: str  # required — file existence checked in app lifespan
    jwt_public_key_path: str  # required — file existence checked in app lifespan
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_seconds: int = 3600
    jwt_expiry_warning_threshold_seconds: int = 300

    # Encryption
    encryption_key: str  # required — must be ≥ 32 bytes for AES-256

    # Redis / Rate limiting
    redis_url: str = "redis://redis:6379"
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # OpenTelemetry
    otel_service_name: str = "fin-loans-contract-processor"
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if len(v.encode()) < 32:
            raise ValueError(
                f"ENCRYPTION_KEY must be at least 32 bytes (got {len(v.encode())})"
            )
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
