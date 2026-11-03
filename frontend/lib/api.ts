export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DocumentInfo = {
  id: string;
  name: string;
  pages: number | null;
  chunks: number;
  created_at: string;
};

export type Citation = {
  number: number;
  document_id: string;
  document_name: string;
  page: number | null;
  snippet: string;
  score: number;
};

export type Answer = { answer: string; grounded: boolean; citations: Citation[] };

export type ResumeMatch = {
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  suggestions: string[];
};

export type MeetingSummary = {
  summary: string;
  decisions: string[];
  action_items: { task: string; owner: string | null; due: string | null }[];
  open_questions: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listDocuments: () => request<DocumentInfo[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentInfo>("/documents", { method: "POST", body: form });
  },
  remove: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  ask: (question: string, documentIds?: string[]) =>
    request<Answer>("/query", json({ question, document_ids: documentIds?.length ? documentIds : null })),
  resumeMatch: (resumeDocumentId: string, jobDescription: string) =>
    request<ResumeMatch>(
      "/tools/resume-match",
      json({ resume_document_id: resumeDocumentId, job_description: jobDescription }),
    ),
  meetingSummary: (documentId: string) =>
    request<MeetingSummary>("/tools/meeting-summary", json({ document_id: documentId })),
};
