import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    demo_mode: bool = False
    osv_api_base: str = "https://api.osv.dev"
    cache_ttl_seconds: int = 300
    exclude_dirs: list[str] = [
        "node_modules",
        ".venv",
        "__pycache__",
        "target",
        ".git",
        ".tox",
        "dist",
        "build",
        ".mypy_cache",
    ]
    log_level: str = "INFO"

    # Access and resource limits (MCP security)
    allowed_base_path: str | None = None  # If set, project_path must be under this directory
    max_input_path_length: int = 4096
    max_exclude_dirs: int = 100
    max_policy_payload_bytes: int = 512 * 1024  # 512 KiB for policy dict or path
    tool_timeout_seconds: float = 120.0  # Per-tool execution timeout; 0 = disabled

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
