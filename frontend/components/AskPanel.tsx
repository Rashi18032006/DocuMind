"use client";

import { FormEvent, useState } from "react";
import { Answer, api } from "@/lib/api";

type Turn = { question: string; answer?: Answer; error?: string };

export default function AskPanel({ scope, hasDocuments }: { scope: string[]; hasDocuments: boolean }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 3 || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [...t, { question: q }]);
    try {
      const answer = await api.ask(q, scope);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, answer } : turn)));
    } catch (err) {
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, error: (err as Error).message } : turn)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ask">
      <div className="thread">
        {turns.length === 0 && (
          <p className="muted empty">
            {hasDocuments
              ? "Ask anything about your documents. Every answer links back to the passage it came from."
              : "Upload a document to get started."}
          </p>
        )}
        {turns.map((turn, i) => (
          <article key={i} className="turn">
            <p className="question">{turn.question}</p>
            {turn.error && <p className="error">{turn.error}</p>}
            {!turn.answer && !turn.error && <p className="muted">Searching your documents…</p>}
            {turn.answer && (
              <div className={`answer${turn.answer.grounded ? "" : " ungrounded"}`}>
                <p>{turn.answer.answer}</p>
                {turn.answer.citations.length > 0 && (
                  <ol className="citations">
                    {turn.answer.citations.map((c) => (
                      <li key={c.number} value={c.number}>
                        <details>
                          <summary>
                            {c.document_name}
                            {c.page ? `, p. ${c.page}` : ""}
                          </summary>
                          <blockquote>{c.snippet}</blockquote>
                        </details>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
      <form className="ask-bar" onSubmit={ask}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={hasDocuments ? "e.g. What is the notice period?" : "Upload a document first"}
          disabled={!hasDocuments}
        />
        <button disabled={!hasDocuments || busy || question.trim().length < 3}>Ask</button>
      </form>
    </section>
  );
}
