"use client";

import axios from "axios";
import { FormEvent, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";

type DocumentItem = {
  id?: number | string;
  name: string;
  title?: string;
  file?: string;
};

type SourceItem = {
  document_id?: number | string;
  title?: string;
  chunk?: number;
};

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: SourceItem[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function getDocumentName(document: DocumentItem) {
  if (document.name) return document.name;
  if (document.title) return document.title;
  if (document.file) return document.file.split("/").pop() ?? document.file;
  return "Untitled document";
}

function normalizeDocuments(data: unknown): DocumentItem[] {
  if (Array.isArray(data)) return data as DocumentItem[];

  if (data && typeof data === "object") {
    const response = data as {
      data?: DocumentItem[];
      documents?: DocumentItem[];
      results?: DocumentItem[];
    };

    return response.data ?? response.documents ?? response.results ?? [];
  }

  return [];
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content: "Upload a PDF, TXT, DOCX, or CSV file, then ask a question about it.",
    },
  ]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [isAnswering, setIsAnswering] = useState(false);
  const [error, setError] = useState("");

  const fetchDocuments = async () => {
    setIsLoadingDocuments(true);
    setError("");

    try {
      const response = await axios.get(`${API_BASE_URL}/api/documents/`);

      setDocuments(normalizeDocuments(response.data));
    } catch (error) {
      console.log(error);
      setError("Cannot load document list. Check Django GET /api/documents/.");
    } finally {
      setIsLoadingDocuments(false);
    }
  };

  const uploadFile = async () => {
    if (!file || isUploading) return;

    setIsUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("title", file.name);
    formData.append("file", file);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/upload/`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      console.log(response.data);

      setFile(null);

      await fetchDocuments();
    } catch (error) {
      console.log(error);
      setError("Upload failed. Check Django POST /api/upload/ and CORS.");
    } finally {
      setIsUploading(false);
    }
  };
  const askQuestion = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const cleanQuestion = question.trim();

    if (!cleanQuestion || isAnswering) return;

    setQuestion("");

    setIsAnswering(true);

    setMessages((current) => [
      ...current,
      {
        id: Date.now(),
        role: "user",
        content: cleanQuestion,
      },
    ]);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/chat/`,
        {
          question: cleanQuestion,
        }
      );

      const data = response.data;

      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data.answer ||
            data.response ||
            data.message ||
            "No answer returned from API.",
          sources: Array.isArray(data.sources) ? data.sources : [],
        },
      ]);
    } catch (error) {
      console.log(error);

      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "Chat API failed.",
        },
      ]);
    } finally {
      setIsAnswering(false);
    }
  };

  const deleteDocument = async (id: number | string) => {
    const confirmDelete = window.confirm(
      "Are you sure you want to delete this document?"
    );

    if (!confirmDelete) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/documents/${id}/`);

      alert("Deleted Successfully");

      fetchDocuments();
    } catch (error) {
      console.log(error);
      alert("Delete Failed");
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Document sidebar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <strong>RAG Studio</strong>
            <span>Django document chat</span>
          </div>
        </div>

        <button className="new-chat" type="button" onClick={fetchDocuments}>
          Refresh Documents
        </button>

        <nav className="nav-list">
          {isLoadingDocuments && <span className="nav-empty">Loading...</span>}

          {!isLoadingDocuments && documents.length === 0 && (
            <span className="nav-empty">No documents uploaded</span>
          )}

          {!isLoadingDocuments &&
            documents.map((document, index) => (
              <div
                key={document.id ?? `${getDocumentName(document)}-${index}`}
                className="document-item"
              >
                <button
                  className="document-name"
                  type="button"
                  title={getDocumentName(document)}
                >
                  {getDocumentName(document)}
                </button>

                <button
                  className="delete-button"
                  type="button"
                  onClick={() => deleteDocument(document.id!)}
                  title="Delete document"
                  disabled={!document.id}
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ))}
        </nav>
      </aside>

      <section className="chat-panel">
        <header className="topbar">
          <div>
            <p>Retrieval-Augmented Generation</p>
            <h1>Ask your uploaded documents</h1>
          </div>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="avatar">{message.role === "user" ? "U" : "AI"}</div>
              <div className="bubble">
                <p>{message.content}</p>

                {message.sources && message.sources.length > 0 && (
                  <div className="sources" aria-label="Answer sources">
                    {message.sources.map((source, index) => (
                      <span key={`${source.document_id ?? source.title}-${source.chunk}-${index}`}>
                        {source.title ?? "Document"}
                        {source.chunk ? ` · chunk ${source.chunk}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}

          {isAnswering && (
            <article className="message assistant">
              <div className="avatar">AI</div>
              <div className="bubble">
                <p>Thinking...</p>
              </div>
            </article>
          )}
        </div>

        <form className="composer" onSubmit={askQuestion}>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about your documents..."
          />
          <button type="submit" disabled={!question.trim() || isAnswering}>
            Send
          </button>
        </form>
      </section>

      <aside className="insights-panel" aria-label="Upload document">
        <section>
          <div className="panel-heading">
            <div>
              <p>Upload</p>
              <strong>Add data file</strong>
            </div>
          </div>

          <div className="upload-box">
            <input
              accept=".pdf,.txt,.doc,.docx,.csv"
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />

            <button type="button" onClick={uploadFile} disabled={!file || isUploading}>
              {isUploading ? "Uploading..." : "Upload"}
            </button>
          </div>

          {file && <p className="selected-file">Selected: {file.name}</p>}
          {error && <p className="error-text">{error}</p>}
        </section>
      </aside>
    </main>
  );
}
