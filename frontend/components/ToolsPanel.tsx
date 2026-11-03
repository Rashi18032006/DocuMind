"use client";

import { useState } from "react";
import { api, DocumentInfo, MeetingSummary, ResumeMatch } from "@/lib/api";

export default function ToolsPanel({ documents }: { documents: DocumentInfo[] }) {
  const [tool, setTool] = useState<"resume" | "meeting">("resume");
  const [docId, setDocId] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [match, setMatch] = useState<ResumeMatch | null>(null);
  const [meeting, setMeeting] = useState<MeetingSummary | null>(null);

  const ready = docId && (tool === "meeting" || jd.trim().length >= 30);

  async function run() {
    setBusy(true);
    setError(null);
    setMatch(null);
    setMeeting(null);
    try {
      if (tool === "resume") setMatch(await api.resumeMatch(docId, jd));
      else setMeeting(await api.meetingSummary(docId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tools">
      <div className="segmented">
        <button className={tool === "resume" ? "on" : ""} onClick={() => setTool("resume")}>
          Resume ↔ job match
        </button>
        <button className={tool === "meeting" ? "on" : ""} onClick={() => setTool("meeting")}>
          Meeting summary
        </button>
      </div>

      <label>
        {tool === "resume" ? "Resume" : "Meeting notes or transcript"}
        <select value={docId} onChange={(e) => setDocId(e.target.value)}>
          <option value="">Choose an uploaded document</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>

      {tool === "resume" && (
        <label>
          Job description
          <textarea rows={7} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the job post here" />
        </label>
      )}

      <button className="primary" disabled={!ready || busy} onClick={run}>
        {busy ? "Working…" : "Run"}
      </button>
      {error && <p className="error">{error}</p>}

      {match && (
        <div className="result">
          <p className="score">
            <strong>{match.match_score}</strong>/100 match
          </p>
          <List title="Matched skills" items={match.matched_skills} />
          <List title="Missing skills" items={match.missing_skills} />
          <List title="Strengths" items={match.strengths} />
          <List title="Suggested edits" items={match.suggestions} />
        </div>
      )}

      {meeting && (
        <div className="result">
          <p>{meeting.summary}</p>
          <List title="Decisions" items={meeting.decisions} />
          <List
            title="Action items"
            items={meeting.action_items.map(
              (a) => `${a.task}${a.owner ? ` (${a.owner})` : ""}${a.due ? `, due ${a.due}` : ""}`,
            )}
          />
          <List title="Open questions" items={meeting.open_questions} />
        </div>
      )}
    </section>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <>
      <h3>{title}</h3>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </>
  );
}
