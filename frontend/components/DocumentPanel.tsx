"use client";

import { useRef, useState } from "react";
import { api, DocumentInfo } from "@/lib/api";

type Props = {
  documents: DocumentInfo[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onChange: () => Promise<void>;
};

export default function DocumentPanel({ documents, selected, onToggle, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(files)) await api.upload(file);
      await onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(id: string) {
    try {
      await api.remove(id);
      await onChange();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <aside className="panel docs">
      <h2>Documents</h2>
      <div
        className={`dropzone${dragging ? " over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          uploadFiles(e.dataTransfer.files);
        }}
      >
        {busy ? "Reading and indexing…" : "Drop PDF, DOCX or TXT files, or click to choose"}
        <input
          ref={input}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          multiple
          hidden
          onChange={(e) => uploadFiles(e.target.files)}
        />
      </div>
      {error && <p className="error">{error}</p>}

      {documents.length === 0 ? (
        <p className="muted">Nothing uploaded yet.</p>
      ) : (
        <ul className="doc-list">
          {documents.map((d) => (
            <li key={d.id}>
              <label>
                <input type="checkbox" checked={selected.has(d.id)} onChange={() => onToggle(d.id)} />
                <span className="doc-name">{d.name}</span>
              </label>
              <span className="muted small">
                {d.pages ? `${d.pages} pages · ` : ""}
                {d.chunks} {d.chunks === 1 ? "chunk" : "chunks"}
              </span>
              <button className="link" onClick={() => remove(d.id)} aria-label={`Delete ${d.name}`}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">Tick documents to search only those. Nothing ticked searches everything.</p>
    </aside>
  );
}
