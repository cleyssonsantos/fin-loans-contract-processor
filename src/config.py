from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me"

    # Database
    database_url: str = "postgresql+asyncpg://loans_user:loans_pass@postgres:5432/loans_db"

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group_id: str = "loans-consumer-group"

    # Auth
    jwt_private_key_path: str = "./secrets/private.pem"
    jwt_public_key_path: str = "./secrets/public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60

    # Encryption
    encryption_key: str = "change-me-32-bytes-key-here-prod!"

    # OpenTelemetry
    otel_service_name: str = "fin-loans-contract-processor"
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
