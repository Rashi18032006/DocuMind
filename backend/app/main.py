"""DocuMind API: upload documents, ask grounded questions, run document automations."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from . import automation
from .ai import ChatModel, Embedder, OpenAIChat, OpenAIEmbedder
from .chunking import chunk_pages
from .config import Settings, get_settings
from .extract import ExtractionError, extract_pages
from .rag import Answer, answer_question
from .store import InMemoryStore, PgVectorStore, VectorStore


class DocumentOut(BaseModel):
    id: str
    name: str
    pages: int | None
    chunks: int
    created_at: str


class QueryIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[str] | None = None


class ResumeMatchIn(BaseModel):
    resume_document_id: str | None = None
    resume_text: str | None = None
    job_description: str = Field(min_length=30)

    @model_validator(mode="after")
    def one_resume(self):
        if not (self.resume_document_id or self.resume_text):
            raise ValueError("Give either resume_document_id or resume_text.")
        return self


class DocumentOrTextIn(BaseModel):
    document_id: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def one_source(self):
        if not (self.document_id or self.text):
            raise ValueError("Give either document_id or text.")
        return self


def create_app(
    settings: Settings | None = None,
    store: VectorStore | None = None,
    embedder: Embedder | None = None,
    llm: ChatModel | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if (embedder is None or llm is None) and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env and add it.")
    store = store or (PgVectorStore(settings.database_url) if settings.database_url else InMemoryStore())
    embedder = embedder or OpenAIEmbedder(settings.openai_api_key, settings.embedding_model)
    llm = llm or OpenAIChat(settings.openai_api_key, settings.chat_model)

    app = FastAPI(title="DocuMind", version="1.0.0", description=__doc__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def text_of(document_id: str) -> str:
        if store.get_document(document_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
        return store.document_text(document_id)

    def automate(fn, *args):
        try:
            return fn(llm, *args)
        except automation.AutomationError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    @app.get("/health")
    def health():
        return {"status": "ok", "store": type(store).__name__}

    @app.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
    async def upload(file: UploadFile = File(...)):
        data = await file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Files are limited to {settings.max_upload_mb} MB."
            )
        name = file.filename or "untitled"
        try:
            pages = extract_pages(name, data)
        except ExtractionError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        embeddings = embedder.embed([c.text for c in chunks])
        page_count = max((p.number or 0) for p in pages) or None
        doc = store.add_document(name, page_count, chunks, embeddings)
        return DocumentOut(**asdict(doc))

    @app.get("/documents", response_model=list[DocumentOut])
    def list_documents():
        return [DocumentOut(**asdict(d)) for d in store.list_documents()]

    @app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_document(document_id: str):
        if not store.delete_document(document_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/query", response_model=Answer)
    def query(body: QueryIn):
        if not store.list_documents():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload a document first.")
        return answer_question(
            body.question,
            store=store,
            embedder=embedder,
            llm=llm,
            top_k=settings.top_k,
            min_similarity=settings.min_similarity,
            document_ids=body.document_ids,
        )

    @app.post("/tools/resume-match", response_model=automation.ResumeMatch)
    def resume_match(body: ResumeMatchIn):
        resume = text_of(body.resume_document_id) if body.resume_document_id else body.resume_text
        return automate(automation.resume_match, resume, body.job_description)

    @app.post("/tools/meeting-summary", response_model=automation.MeetingSummary)
    def meeting_summary(body: DocumentOrTextIn):
        return automate(automation.meeting_summary, text_of(body.document_id) if body.document_id else body.text)

    @app.post("/tools/report", response_model=automation.Report)
    def report(body: DocumentOrTextIn):
        return automate(automation.report, text_of(body.document_id) if body.document_id else body.text)

    return app
# Run with:  uvicorn app.main:create_app --factory --reload
