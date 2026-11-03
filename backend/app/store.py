"""Vector storage. PgVectorStore talks to Supabase Postgres; InMemoryStore is for local runs and tests."""

from __future__ import annotations

import math
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .chunking import Chunk


@dataclass(frozen=True)
class DocumentInfo:
    id: str
    name: str
    pages: int | None
    chunks: int
    created_at: str


@dataclass(frozen=True)
class Hit:
    document_id: str
    document_name: str
    chunk_index: int
    page: int | None
    text: str
    score: float  # cosine similarity, 1.0 = identical


class VectorStore(Protocol):
    def add_document(
        self, name: str, pages: int | None, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> DocumentInfo: ...
    def list_documents(self) -> list[DocumentInfo]: ...
    def get_document(self, document_id: str) -> DocumentInfo | None: ...
    def document_text(self, document_id: str) -> str: ...
    def delete_document(self, document_id: str) -> bool: ...
    def search(
        self, embedding: list[float], k: int, document_ids: list[str] | None = None
    ) -> list[Hit]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InMemoryStore:
    def __init__(self) -> None:
        self._docs: dict[str, DocumentInfo] = {}
        self._rows: dict[str, list[tuple[Chunk, list[float]]]] = {}
        self._lock = threading.Lock()

    def add_document(self, name, pages, chunks, embeddings):
        doc = DocumentInfo(str(uuid.uuid4()), name, pages, len(chunks), _now())
        with self._lock:
            self._docs[doc.id] = doc
            self._rows[doc.id] = list(zip(chunks, embeddings))
        return doc

    def list_documents(self):
        return sorted(self._docs.values(), key=lambda d: d.created_at, reverse=True)

    def get_document(self, document_id):
        return self._docs.get(document_id)

    def document_text(self, document_id):
        return "\n\n".join(chunk.text for chunk, _ in self._rows.get(document_id, []))

    def delete_document(self, document_id):
        with self._lock:
            self._rows.pop(document_id, None)
            return self._docs.pop(document_id, None) is not None

    def search(self, embedding, k, document_ids=None):
        hits: list[Hit] = []
        for doc_id, rows in self._rows.items():
            if document_ids and doc_id not in document_ids:
                continue
            name = self._docs[doc_id].name
            for chunk, vector in rows:
                score = _cosine(embedding, vector)
                hits.append(Hit(doc_id, name, chunk.index, chunk.page, chunk.text, score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


class PgVectorStore:
    """Postgres + pgvector (Supabase). Tables are created by supabase/schema.sql."""

    def __init__(self, database_url: str):
        import psycopg

        self._psycopg = psycopg
        self._url = database_url

    def _connect(self):
        return self._psycopg.connect(self._url, autocommit=True)

    def add_document(self, name, pages, chunks, embeddings):
        with self._connect() as conn, conn.transaction():
            row = conn.execute(
                "insert into documents (name, pages, chunk_count) values (%s, %s, %s) "
                "returning id, created_at",
                (name, pages, len(chunks)),
            ).fetchone()
            doc_id, created = str(row[0]), row[1]
            with conn.cursor() as cur:
                cur.executemany(
                    "insert into chunks (document_id, chunk_index, page, content, embedding) "
                    "values (%s, %s, %s, %s, %s::vector)",
                    [
                        (doc_id, c.index, c.page, c.text, _vector_literal(e))
                        for c, e in zip(chunks, embeddings)
                    ],
                )
        return DocumentInfo(doc_id, name, pages, len(chunks), created.isoformat(timespec="seconds"))

    def list_documents(self):
        with self._connect() as conn:
            rows = conn.execute(
                "select id, name, pages, chunk_count, created_at from documents order by created_at desc"
            ).fetchall()
        return [DocumentInfo(str(r[0]), r[1], r[2], r[3], r[4].isoformat(timespec="seconds")) for r in rows]

    def get_document(self, document_id):
        with self._connect() as conn:
            r = conn.execute(
                "select id, name, pages, chunk_count, created_at from documents where id = %s",
                (document_id,),
            ).fetchone()
        return DocumentInfo(str(r[0]), r[1], r[2], r[3], r[4].isoformat(timespec="seconds")) if r else None

    def document_text(self, document_id):
        with self._connect() as conn:
            rows = conn.execute(
                "select content from chunks where document_id = %s order by chunk_index", (document_id,)
            ).fetchall()
        return "\n\n".join(r[0] for r in rows)

    def delete_document(self, document_id):
        with self._connect() as conn:
            cur = conn.execute("delete from documents where id = %s", (document_id,))
            return cur.rowcount > 0

    def search(self, embedding, k, document_ids=None):
        sql = (
            "select c.document_id, d.name, c.chunk_index, c.page, c.content, "
            "1 - (c.embedding <=> %(q)s::vector) as score "
            "from chunks c join documents d on d.id = c.document_id "
        )
        params: dict = {"q": _vector_literal(embedding), "k": k}
        if document_ids:
            sql += "where c.document_id = any(%(ids)s::uuid[]) "
            params["ids"] = document_ids
        sql += "order by c.embedding <=> %(q)s::vector limit %(k)s"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Hit(str(r[0]), r[1], r[2], r[3], r[4], float(r[5])) for r in rows]
