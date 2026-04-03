import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação carregadas a partir de variáveis de ambiente."""

    jwt_secret: str = Field(
        default="change-me-in-production",
        alias="JWT_SECRET",
        description="Chave secreta usada para assinar tokens JWT.",
    )
    database_url: str = Field(
        default=(
            "postgresql+asyncpg://rpg_user:${POSTGRES_PASSWORD}@postgres:5432/rpg_platform"
        ),
        alias="DATABASE_URL",
        description="URL de conexão com o banco de dados PostgreSQL (asyncpg).",
    )
    debug: bool = Field(default=False, alias="DEBUG")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()


settings: Settings = get_settings()
