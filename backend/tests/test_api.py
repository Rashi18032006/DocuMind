import io

from docx import Document

from app.chunking import chunk_pages
from app.extract import Page
from tests.conftest import upload

LEAVE_POLICY = (
    b"Leave Policy\n"
    b"Employees get 24 days of paid annual leave per calendar year.\n"
    b"Unused leave can be carried forward up to a maximum of 10 days.\n"
)
TRAVEL_POLICY = b"Travel Policy\nTrain travel is reimbursed in AC 2-tier class for trips over 300 km.\n"


def test_upload_list_delete(client):
    res = upload(client, "leave.txt", LEAVE_POLICY)
    assert res.status_code == 201
    doc = res.json()
    assert doc["name"] == "leave.txt" and doc["chunks"] >= 1

    assert [d["id"] for d in client.get("/documents").json()] == [doc["id"]]
    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    assert client.get("/documents").json() == []
    assert client.delete(f"/documents/{doc['id']}").status_code == 404


def test_docx_upload(client):
    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Quarterly review notes")
    d.add_paragraph("Revenue grew twelve percent in the north region.")
    d.save(buf)
    res = upload(client, "notes.docx", buf.getvalue())
    assert res.status_code == 201
    assert res.json()["pages"] is None


def test_rejects_unsupported_and_empty_files(client):
    res = upload(client, "photo.png", b"\x89PNG....")
    assert res.status_code == 400 and "Unsupported file type" in res.json()["detail"]

    res = upload(client, "blank.txt", b"   \n\n  ")
    assert res.status_code == 400 and "No readable text" in res.json()["detail"]

    res = upload(client, "empty.pdf", b"")
    assert res.status_code == 400 and "empty" in res.json()["detail"]


def test_query_answers_with_citation_to_the_right_document(client, chat):
    leave = upload(client, "leave.txt", LEAVE_POLICY).json()
    upload(client, "travel.txt", TRAVEL_POLICY)
    chat.replies.append(
        {"answer": "Employees get 24 days of paid annual leave per year [1].", "answerable": True, "sources_used": [1]}
    )

    res = client.post("/query", json={"question": "How many days of paid annual leave do employees get?"})
    body = res.json()

    assert res.status_code == 200
    assert body["grounded"] is True
    assert body["citations"][0]["document_id"] == leave["id"]
    assert "Sources:" in chat.calls[0][1]  # the model only ever sees retrieved sources


def test_low_relevance_question_skips_the_model(client, chat):
    upload(client, "leave.txt", LEAVE_POLICY)
    res = client.post("/query", json={"question": "What is the boiling point of mercury?"})
    body = res.json()
    assert body["grounded"] is False and body["citations"] == []
    assert chat.calls == []  # no tokens spent on an unanswerable question


def test_model_saying_unanswerable_is_not_grounded(client, chat):
    upload(client, "leave.txt", LEAVE_POLICY)
    chat.replies.append({"answer": "The sources don't say.", "answerable": False, "sources_used": []})
    body = client.post("/query", json={"question": "Can unused annual leave be encashed?"}).json()
    assert body["grounded"] is False and body["citations"] == []


def test_query_can_be_scoped_to_documents(client, chat):
    upload(client, "leave.txt", LEAVE_POLICY)
    travel = upload(client, "travel.txt", TRAVEL_POLICY).json()
    chat.replies.append({"answer": "Not covered.", "answerable": False, "sources_used": []})
    body = client.post(
        "/query", json={"question": "How many days of annual leave?", "document_ids": [travel["id"]]}
    ).json()
    assert all(c["document_id"] == travel["id"] for c in body["citations"])


def test_query_needs_a_document(client):
    res = client.post("/query", json={"question": "anything at all?"})
    assert res.status_code == 400


def test_resume_match_validates_and_retries(client, chat):
    resume = upload(client, "resume.txt", b"Python developer. FastAPI, PostgreSQL, React. Built RAG apps.").json()
    chat.replies += [
        {"match_score": "high"},  # malformed: triggers one retry
        {
            "match_score": 78,
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": ["Docker"],
            "strengths": ["Shipped RAG apps"],
            "suggestions": ["Add a Docker project"],
        },
    ]
    res = client.post(
        "/tools/resume-match",
        json={"resume_document_id": resume["id"], "job_description": "Backend intern: Python, FastAPI, Docker, SQL."},
    )
    assert res.status_code == 200 and res.json()["match_score"] == 78
    assert len(chat.calls) == 2


def test_meeting_summary_from_text(client, chat):
    chat.replies.append(
        {
            "summary": "Team agreed the launch date.",
            "decisions": ["Launch on 12 Dec"],
            "action_items": [{"task": "Draft release notes", "owner": "Asha", "due": None}],
            "open_questions": [],
        }
    )
    res = client.post("/tools/meeting-summary", json={"text": "Asha will draft release notes. Launch is 12 Dec."})
    assert res.status_code == 200 and res.json()["action_items"][0]["owner"] == "Asha"


def test_tool_with_unknown_document(client):
    res = client.post("/tools/report", json={"document_id": "nope"})
    assert res.status_code == 404


def test_chunking_overlaps_and_keeps_pages():
    text = " ".join(f"word{i}" for i in range(600))
    chunks = chunk_pages([Page(3, text)], size=500, overlap=100)
    assert len(chunks) > 1
    assert all(c.page == 3 and len(c.text) <= 500 for c in chunks)
    assert chunks[0].text.split()[-1] in chunks[1].text  # overlap carries context across the cut
