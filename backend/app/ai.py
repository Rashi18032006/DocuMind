"""Thin wrappers around the OpenAI API, so the rest of the app (and the tests) can swap them out."""

from __future__ import annotations

import json
from typing import Any, Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatModel(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, batch_size: int = 96):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._batch = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch):
            batch = texts[start : start + self._batch]
            response = self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend(item.embedding for item in response.data)
        return vectors


class OpenAIChat:
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("The model returned malformed JSON.") from exc
