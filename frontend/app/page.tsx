"use client";

import { useCallback, useEffect, useState } from "react";
import AskPanel from "@/components/AskPanel";
import DocumentPanel from "@/components/DocumentPanel";
import ToolsPanel from "@/components/ToolsPanel";
import { api, API_URL, DocumentInfo } from "@/lib/api";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<"ask" | "tools">("ask");
  const [offline, setOffline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
      setSelected((s) => new Set([...s].filter((id) => docs.some((d) => d.id === id))));
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <main className="shell">
      <header className="top">
        <h1>
          Docu<span>Mind</span>
        </h1>
        <p className="muted">Ask your documents. Get answers with sources.</p>
        <nav className="tabs">
          <button className={tab === "ask" ? "on" : ""} onClick={() => setTab("ask")}>
            Ask
          </button>
          <button className={tab === "tools" ? "on" : ""} onClick={() => setTab("tools")}>
            Automations
          </button>
        </nav>
      </header>

      {offline && (
        <p className="error banner">
          Can&apos;t reach the API at {API_URL}. Start the backend, or set NEXT_PUBLIC_API_URL.
        </p>
      )}

      <div className="layout">
        <DocumentPanel documents={documents} selected={selected} onToggle={toggle} onChange={refresh} />
        <div className="panel main">
          {tab === "ask" ? (
            <AskPanel scope={[...selected]} hasDocuments={documents.length > 0} />
          ) : (
            <ToolsPanel documents={documents} />
          )}
        </div>
      </div>
    </main>
  );
}
