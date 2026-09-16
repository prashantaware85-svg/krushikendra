/**
 * Analysis Result (auth-only): uncertain observation + quality + sources,
 * safe next steps, and a Krushi Mitra follow-up link. No prescriptions.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type CropAnalysis,
} from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function AnalysisPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [analysis, setAnalysis] = useState<CropAnalysis | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const row = await api.getAnalysis(token, params.id);
      setAnalysis(row);
      // Authenticated blob fetch (no public file URLs by design).
      const res = await fetch(api.analysisImageUrl(params.id), {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (res.ok) {
        const blob = await res.blob();
        setPhotoUrl(URL.createObjectURL(blob));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
    return () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  async function onRetry() {
    const token = getStoredToken();
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    try {
      setAnalysis(await api.reanalyze(token, params.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!window.confirm(t.deleteAnalysisConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteAnalysis(token, params.id);
      router.push("/crop-check");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href="/crop-check">← {t.cropCheckTitle}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!analysis ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <section className="card">
            <h1>🔎 {t.cropCheckTitle}</h1>
            {photoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photoUrl} alt="" className="result-img" />
            ) : null}

            {analysis.status === "failed" ? (
              <>
                <p className="form-error">{t.analysisFailed}</p>
                <button
                  className="btn"
                  type="button"
                  disabled={busy}
                  onClick={onRetry}
                >
                  {t.retryAnalysis}
                </button>
              </>
            ) : (
              <>
                <KV k={t.possibleCondition} v={analysis.possible_condition} t={t} />
                <KV
                  k={t.confidenceLabel}
                  v={
                    analysis.confidence !== null
                      ? `${Math.round(Number(analysis.confidence) * 100)}%`
                      : null
                  }
                  t={t}
                />
                <KV
                  k={t.observedLabel}
                  v={analysis.observations.join(" ") || null}
                  t={t}
                />
                {analysis.needs_info.length > 0 ? (
                  <KV k={t.needsInfoLabel} v={analysis.needs_info.join(" ")} />
                ) : null}
                {analysis.next_steps.length > 0 ? (
                  <div>
                    <p>
                      <strong>{t.nextStepsLabel}:</strong>
                    </p>
                    <ul>
                      {analysis.next_steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <KV
                  k={t.qualityGood}
                  v={
                    analysis.image_quality === "poor"
                      ? `${t.qualityPoor}. ${analysis.quality_notes ?? ""} ${t.qualityRetake}`
                      : t.qualityGood
                  }
                />
                {analysis.sources.length > 0 ? (
                  <p className="muted small">
                    📚 {t.aiSources}:
                    <br />
                    {analysis.sources.map((s) => (
                      <span key={s.chunk_id}>
                        - {s.title} ({s.source_name})
                        <br />
                      </span>
                    ))}
                  </p>
                ) : null}
                <p className="disclaimer">⚠️ {analysis.disclaimer}</p>
                {analysis.is_mock ? (
                  <p className="muted small">[MOCK — development only]</p>
                ) : null}
                <div className="card-actions">
                  <Link
                    className="btn link-btn"
                    href="/ai"
                  >
                    {t.askMitra} →
                  </Link>
                  <button
                    className="btn-danger"
                    type="button"
                    onClick={onDelete}
                  >
                    {t.deleteAnalysis}
                  </button>
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </AuthGate>
  );
}

function KV({ k, v, t }: { k: string; v: string | null | undefined; t?: { notSet: string } }) {
  return (
    <p>
      <strong>{k}:</strong> {v ?? t?.notSet ?? "—"}
    </p>
  );
}
