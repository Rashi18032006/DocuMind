"""Retrieval-augmented answering: find the relevant chunks, answer only from them, cite them."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .ai import ChatModel, Embedder
from .store import Hit, VectorStore

NOT_FOUND = "I couldn't find this in your documents. Try rephrasing, or upload the document that covers it."

SYSTEM_PROMPT = """You answer questions using ONLY the numbered sources provided.
Rules:
- Every factual sentence must end with the source number(s) it came from, like [1] or [2][3].
- If the sources don't contain the answer, say so plainly and set "answerable" to false.
- Never use outside knowledge. Be concise.
Reply as JSON: {"answer": string, "answerable": boolean, "sources_used": [numbers]}"""


class Citation(BaseModel):
    number: int
    document_id: str
    document_name: str
    page: int | None
    snippet: str
    score: float


class Answer(BaseModel):
    answer: str
    grounded: bool
    citations: list[Citation] = Field(default_factory=list)


def answer_question(
    question: str,
    *,
    store: VectorStore,
    embedder: Embedder,
    llm: ChatModel,
    top_k: int,
    min_similarity: float,
    document_ids: list[str] | None = None,
) -> Answer:
    question = question.strip()
    [query_vector] = embedder.embed([question])
    hits = [h for h in store.search(query_vector, top_k, document_ids) if h.score >= min_similarity]

    # Nothing relevant: say so without spending a model call (and without inventing an answer).
    if not hits:
        return Answer(answer=NOT_FOUND, grounded=False)

    sources = "\n\n".join(
        f"[{i}] {h.document_name}{f', page {h.page}' if h.page else ''}\n{h.text}"
        for i, h in enumerate(hits, start=1)
    )
    result = llm.complete_json(SYSTEM_PROMPT, f"Sources:\n{sources}\n\nQuestion: {question}")

    text = str(result.get("answer", "")).strip() or NOT_FOUND
    answerable = bool(result.get("answerable", True))
    used = _used_sources(result.get("sources_used"), text, len(hits))
    if not answerable or not used:
        return Answer(answer=text if not answerable else NOT_FOUND, grounded=False)

    return Answer(answer=text, grounded=True, citations=[_cite(n, hits[n - 1]) for n in used])


def _used_sources(declared, text: str, count: int) -> list[int]:
    numbers = set()
    if isinstance(declared, list):
        numbers.update(n for n in declared if isinstance(n, int))
    numbers.update(int(n) for n in re.findall(r"\[(\d+)\]", text))
    return sorted(n for n in numbers if 1 <= n <= count)


def _cite(number: int, hit: Hit) -> Citation:
    snippet = hit.text if len(hit.text) <= 280 else hit.text[:277].rsplit(" ", 1)[0] + "..."
    return Citation(
        number=number,
        document_id=hit.document_id,
        document_name=hit.document_name,
        page=hit.page,
        snippet=snippet,
        score=round(hit.score, 3),
    )
