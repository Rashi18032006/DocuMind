"""Runtime settings, read once from the environment (or a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = ""
    database_url: str = ""  # Supabase Postgres connection string; empty = in-memory store
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o-mini"
    chunk_size: int = 900  # characters per chunk
    chunk_overlap: int = 150
    top_k: int = 5
    min_similarity: float = 0.30  # below this a hit is treated as irrelevant
    max_upload_mb: int = 15
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        embedding_model=os.getenv("EMBEDDING_MODEL", Settings.embedding_model),
        chat_model=os.getenv("CHAT_MODEL", Settings.chat_model),
        top_k=int(os.getenv("TOP_K", Settings.top_k)),
        min_similarity=float(os.getenv("MIN_SIMILARITY", Settings.min_similarity)),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
