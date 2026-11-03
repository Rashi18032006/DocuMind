"""Test doubles: a deterministic bag-of-words embedder and a scripted chat model."""

from __future__ import annotations

import hashlib
import math
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import InMemoryStore

DIM = 256


class FakeEmbedder:
    def embed(self, texts):
        return [self._vector(t) for t in texts]

    @staticmethod
    def _vector(text):
        v = [0.0] * DIM
        for word in re.findall(r"[a-z]{3,}", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class FakeChat:
    """Returns queued replies in order; records every prompt it was sent."""

    def __init__(self):
        self.replies: list[dict] = []
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system, user):
        self.calls.append((system, user))
        return self.replies.pop(0) if self.replies else {}


@pytest.fixture
def chat():
    return FakeChat()


@pytest.fixture
def client(chat):
    settings = Settings(min_similarity=0.2, top_k=3)
    app = create_app(settings, InMemoryStore(), FakeEmbedder(), chat)
    return TestClient(app)


def upload(client, name, content: bytes):
    return client.post("/documents", files={"file": (name, content)})
