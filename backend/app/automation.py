"""Document automation: structured outputs for common jobs, validated with Pydantic."""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from .ai import ChatModel

MAX_CHARS = 24_000  # keep prompts well inside the model's context window


class AutomationError(RuntimeError):
    pass


class ResumeMatch(BaseModel):
    match_score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    suggestions: list[str]


class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    due: str | None = None


class MeetingSummary(BaseModel):
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]


class Report(BaseModel):
    title: str
    executive_summary: str
    key_points: list[str]
    risks: list[str]
    recommendations: list[str]


def resume_match(llm: ChatModel, resume: str, job_description: str) -> ResumeMatch:
    system = (
        "You compare a resume against a job description. Judge only from the two texts. "
        "Return JSON with: match_score (0-100 integer), matched_skills, missing_skills, "
        "strengths (what makes the candidate stand out for this role), suggestions "
        "(concrete edits to the resume). Lists of short strings."
    )
    user = f"RESUME:\n{_trim(resume)}\n\nJOB DESCRIPTION:\n{_trim(job_description)}"
    return _run(llm, system, user, ResumeMatch)


def meeting_summary(llm: ChatModel, transcript: str) -> MeetingSummary:
    system = (
        "You summarise meeting notes or transcripts. Return JSON with: summary (3-5 sentences), "
        "decisions, action_items (objects with task, owner, due; use null when not stated), "
        "open_questions. Do not invent owners or dates."
    )
    return _run(llm, system, _trim(transcript), MeetingSummary)


def report(llm: ChatModel, text: str) -> Report:
    system = (
        "You turn a document into a short briefing report. Return JSON with: title, "
        "executive_summary (one paragraph), key_points, risks, recommendations. "
        "Use only what the document says."
    )
    return _run(llm, system, _trim(text), Report)


def _run(llm: ChatModel, system: str, user: str, model: type[BaseModel]):
    if not user.strip():
        raise AutomationError("There is no text to work with.")
    data = llm.complete_json(system, user)
    try:
        return model.model_validate(data)
    except ValidationError:
        # One retry with the validation problem spelled out usually fixes a malformed reply.
        data = llm.complete_json(
            system + f"\nYour previous reply did not match the schema {model.model_json_schema()}. "
            "Reply again with valid JSON only.",
            user,
        )
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise AutomationError("The model's reply didn't match the expected format.") from exc


def _trim(text: str) -> str:
    text = text.strip()
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n[truncated]"
