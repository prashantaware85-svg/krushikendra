/**
 * Krushi Mitra chat (auth-only): conversations, farm/crop context,
 * source-attributed answers. Marathi-first, mobile-friendly.
 * Voice button is a future placeholder (disabled, labelled).
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type AIConversation,
  type AIConversationDetail,
  type AIMessage,
  type Crop,
  type Farm,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function AIPage() {
  const { t, language } = useAuth();
  const [conversations, setConversations] = useState<AIConversation[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [farmId, setFarmId] = useState("");
  const [crops, setCrops] = useState<Crop[]>([]);
  const [cropId, setCropId] = useState("");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadList = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [convs, farmList] = await Promise.all([
        api.listConversations(token),
        api.listFarms(token).catch(() => [] as Farm[]),
      ]);
      setConversations(convs);
      setFarms(farmList);
      if (!activeId && convs.length > 0) {
        setActiveId(convs[0].id);
      } else if (convs.length === 0) {
        setMessages([]);
        setActiveId(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [activeId]);

  const loadDetail = useCallback(async (id: string) => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const detail: AIConversationDetail = await api.getConversation(token, id);
      setMessages(detail.messages);
      setActiveId(id);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (activeId) loadDetail(activeId);
  }, [activeId, loadDetail]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Crops follow the selected farm (explicit ids only — never guessed).
  useEffect(() => {
    const token = getStoredToken();
    if (!token || !farmId) {
      setCrops([]);
      setCropId("");
      return;
    }
    api
      .listCrops(token, farmId)
      .then((list) => {
        setCrops(list);
        setCropId("");
      })
      .catch(() => setCrops([]));
  }, [farmId]);

  async function newChat() {
    const token = getStoredToken();
    if (!token) return;
    try {
      const conv = await api.createConversation(token, language);
      setConversations((prev) => (prev ? [conv, ...prev] : [conv]));
      setActiveId(conv.id);
      setMessages([]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function send(retryText?: string) {
    const text = (retryText ?? input).trim();
    if (!text || busy) return;
    const token = getStoredToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      let id = activeId;
      if (!id) {
        const conv = await api.createConversation(token, language);
        id = conv.id;
        setConversations((prev) => (prev ? [conv, ...prev] : [conv]));
        setActiveId(id);
      }
      const reply = await api.sendChatMessage(token, id, {
        message: text,
        farm_id: farmId || undefined,
        crop_id: cropId || undefined,
        language,
      });
      setInput("");
      setMessages((prev) => [
        ...prev,
        {
          id: `local-${Date.now()}`,
          conversation_id: id as string,
          role: "user",
          content: text,
          sources: [],
        },
        reply.message,
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function removeChat(id: string) {
    if (!window.confirm(t.aiDeleteConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteConversation(token, id);
      setConversations((prev) => (prev ? prev.filter((c) => c.id !== id) : prev));
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main chat-wrap">
        <div className="page-head">
          <h1>🤖 {t.aiTitle}</h1>
          <button className="btn add-btn" type="button" onClick={newChat}>
            + {t.aiNewChat}
          </button>
        </div>

        <div className="chip-row">
          <select
            aria-label={t.aiFarmLabel}
            value={farmId}
            onChange={(e) => setFarmId(e.target.value)}
            className="chip-select"
          >
            <option value="">
              {t.aiFarmLabel}: —
            </option>
            {farms.map((f) => (
              <option key={f.id} value={f.id}>
                {f.farm_name}
              </option>
            ))}
          </select>
          <select
            aria-label={t.aiCropLabel}
            value={cropId}
            onChange={(e) => setCropId(e.target.value)}
            className="chip-select"
            disabled={!farmId}
          >
            <option value="">{t.aiAnyCrop}</option>
            {crops.map((c) => (
              <option key={c.id} value={c.id}>
                {c.crop_name}
              </option>
            ))}
          </select>
        </div>

        <div className="chip-row">
          <select
            aria-label={t.aiTitle}
            value={activeId ?? ""}
            onChange={(e) => e.target.value && loadDetail(e.target.value)}
            className="chip-select"
          >
            <option value="">{t.aiNewChat}…</option>
            {(conversations ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {(c.title || t.aiTitle).slice(0, 30)}
              </option>
            ))}
          </select>
          {activeId ? (
            <button type="button" className="chip" onClick={() => removeChat(activeId)}>
              {t.aiDeleteChat}
            </button>
          ) : null}
        </div>

        <section className="card chat-box">
          {messages.length === 0 && !busy ? (
            <p className="muted">👋 {t.aiGreeting}</p>
          ) : null}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "msg-user" : "msg-ai"}>
              <p className="msg-who">{m.role === "user" ? "👨‍🌾" : "🤖"}</p>
              <p className="msg-text">{m.content}</p>
              {m.role === "assistant" && m.sources.length > 0 ? (
                <p className="muted small">
                  📚 {t.aiSources}:
                  <br />
                  {m.sources.map((s) => (
                    <span key={s.chunk_id}>
                      - {s.title} ({s.source_name})
                      <br />
                    </span>
                  ))}
                </p>
              ) : null}
            </div>
          ))}
          {busy ? <p className="muted">{t.aiThinking}</p> : null}
          <div ref={bottomRef} />
        </section>

        {error ? (
          <p className="form-error">
            {error}{" "}
            <button type="button" className="chip" onClick={() => input.trim() && send()}>
              {t.aiRetry}
            </button>
          </p>
        ) : null}

        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t.aiPlaceholder}
            maxLength={2000}
            aria-label={t.aiPlaceholder}
          />
          <button
            type="button"
            className="btn-secondary chat-voice"
            title={t.aiVoiceSoon}
            disabled
          >
            🎤
          </button>
          <button className="btn chat-send" type="submit" disabled={busy || !input.trim()}>
            {t.aiSend}
          </button>
        </form>
      </main>
    </AuthGate>
  );
}
