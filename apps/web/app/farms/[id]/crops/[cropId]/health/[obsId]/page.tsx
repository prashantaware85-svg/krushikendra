/**
 * Observation Details (auth-only): record + photos + linked analysis +
 * actions taken + Krushi Mitra link. Display only — never treatment advice.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "../../../../../../../components/AuthGate";
import {
  observationSourceLabel,
  observationStatusLabel,
  observationTypeLabel,
  severityDot,
  severityLabel,
} from "../../../../../../../components/healthLabels";
import {
  ApiError,
  api,
  getStoredToken,
  type Crop,
  type Farm,
  type HealthAction,
  type HealthObservation,
} from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function ObservationPage({
  params,
}: {
  params: { id: string; cropId: string; obsId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [obs, setObs] = useState<HealthObservation | null>(null);
  const [crop, setCrop] = useState<Crop | null>(null);
  const [farm, setFarm] = useState<Farm | null>(null);
  const [actions, setActions] = useState<HealthAction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Inline add-action form state (record what was done — never advice).
  const [actionText, setActionText] = useState("");
  const [actionDate, setActionDate] = useState("");
  // Photo upload state (up to 3 total per observation).
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [o, c, f, a] = await Promise.all([
        api.getObservation(token, params.id, params.cropId, params.obsId),
        api.getCrop(token, params.id, params.cropId),
        api.getFarm(token, params.id),
        api.listActions(token, params.obsId).catch(() => [] as HealthAction[]),
      ]);
      setObs(o);
      setCrop(c);
      setFarm(f);
      setActions(a);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.obsId]);

  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(status: string) {
    const token = getStoredToken();
    if (!token || busy) return;
    setBusy(true);
    try {
      setObs(
        await api.updateObservation(token, params.id, params.cropId, params.obsId, {
          status,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!window.confirm(t.deleteObservationConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteObservation(token, params.id, params.cropId, params.obsId);
      router.push(`/farms/${params.id}/crops/${params.cropId}/health`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function addAction(e: FormEvent) {
    e.preventDefault();
    const token = getStoredToken();
    if (!token || !actionText.trim() || !actionDate) return;
    setBusy(true);
    try {
      const created = await api.createAction(token, params.obsId, {
        action_date: actionDate,
        action_type: "monitoring",
        description: actionText.trim(),
      });
      setActions((prev) => (prev ? [created, ...prev] : [created]));
      setActionText("");
      setActionDate("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function removeAction(actionId: string) {
    if (!window.confirm(t.deleteActionConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteAction(token, params.obsId, actionId);
      setActions((prev) => (prev ? prev.filter((a) => a.id !== actionId) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function addPhotos(files: FileList | null) {
    if (!files || files.length === 0) return;
    const token = getStoredToken();
    if (!token) return;
    setUploading(true);
    try {
      setObs(
        await api.uploadObservationPhotos(
          token,
          params.id,
          params.cropId,
          params.obsId,
          Array.from(files),
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}/crops/${params.cropId}/health`}>
            ← {t.backToHealth}
          </Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!obs ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="hero">
              <h1>
                {severityDot(obs.severity)} {displayName(obs)}
              </h1>
              <p>
                {obs.observation_date} · {observationTypeLabel(t, obs.observation_type)} ·{" "}
                {t.severityLabel}: {severityLabel(t, obs.severity)}
              </p>
            </section>

            <div className="grid">
              <div className="card">
                <h2>{t.cropName}</h2>
                <KV k={t.cropName} v={crop?.crop_name} />
                <KV k={t.farmName} v={farm?.farm_name} />
                <KV k={t.observationType} v={observationTypeLabel(t, obs.observation_type)} />
                <KV k={t.obsSource} v={observationSourceLabel(t, obs.source)} />
                <KV
                  k={t.affectedArea}
                  v={
                    obs.affected_area
                      ? `${obs.affected_area} ${obs.affected_area_unit ?? ""}`.trim()
                      : null
                  }
                  t={t}
                />
                <KV k={t.symptomsLabel} v={obs.symptoms} t={t} />
                <KV k={t.soilNotes} v={obs.notes} t={t} />
                <KV k={t.obsStatus} v={observationStatusLabel(t, obs.status)} />
                <div className="card-actions">
                  <button
                    className="btn-secondary"
                    type="button"
                    disabled={busy}
                    onClick={() => setStatus("monitoring")}
                  >
                    {t.markMonitoring}
                  </button>
                  <button
                    className="btn-secondary"
                    type="button"
                    disabled={busy}
                    onClick={() => setStatus("resolved")}
                  >
                    {t.markResolved}
                  </button>
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() =>
                      router.push(
                        `/farms/${params.id}/crops/${params.cropId}/health/${params.obsId}/edit`,
                      )
                    }
                  >
                    {t.edit}
                  </button>
                  <button className="btn-danger" type="button" onClick={onDelete}>
                    {t.deleteObservation}
                  </button>
                </div>
              </div>

              <div className="card">
                <h2>📷 {t.obsPhotos}</h2>
                {obs.has_photos ? (
                  <p className="muted">✓</p>
                ) : (
                  <p className="muted">{t.noAnalyses}</p>
                )}
                <label className="field">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    disabled={uploading}
                    onChange={(e) => addPhotos(e.target.files)}
                  />
                </label>
              </div>

              {obs.linked_analysis ? (
                <div className="card">
                  <h2>📸 {t.linkedAnalysisTitle}</h2>
                  <p>
                    {obs.linked_analysis.possible_condition ?? t.notSet} ·{" "}
                    {obs.linked_analysis.confidence !== null
                      ? `${Math.round(Number(obs.linked_analysis.confidence) * 100)}%`
                      : t.notSet}
                  </p>
                  <p className="muted small">{t.cropCheckHint}</p>
                </div>
              ) : null}

              <div className="card">
                <h2>🧾 {t.healthActions}</h2>
                {actions === null ? (
                  <p className="muted">{t.loading}</p>
                ) : actions.length === 0 ? (
                  <p className="muted">{t.noActions}</p>
                ) : (
                  actions.map((a) => (
                    <p key={a.id}>
                      <strong>{a.description}</strong> · {a.action_date}{" "}
                      <button
                        type="button"
                        className="link-btn-plain"
                        onClick={() => removeAction(a.id)}
                      >
                        [{t.deleteAction}]
                      </button>
                    </p>
                  ))
                )}
                <form onSubmit={addAction}>
                  <label className="field">
                    <span>{t.addAction}</span>
                    <input
                      value={actionText}
                      onChange={(e) => setActionText(e.target.value)}
                      placeholder={t.actionDescriptionPlaceholder}
                      maxLength={2000}
                      required
                    />
                  </label>
                  <label className="field">
                    <span>{t.actionDate}</span>
                    <input
                      type="date"
                      value={actionDate}
                      onChange={(e) => setActionDate(e.target.value)}
                      required
                    />
                  </label>
                  <button className="btn" type="submit" disabled={busy}>
                    {t.addAction}
                  </button>
                </form>
              </div>

              <div className="card">
                <h2>🤖 {t.aiTitle}</h2>
                <p>
                  <Link href="/ai">{t.askMitra} →</Link>
                </p>
                <p className="muted small">{t.cropCheckHint}</p>
              </div>
            </div>
          </>
        )}
      </main>
    </AuthGate>
  );
}

function displayName(o: { observed_name: string | null; pest_name: string | null; disease_name: string | null; observation_type: string }): string {
  return o.observed_name ?? o.pest_name ?? o.disease_name ?? o.observation_type;
}

function KV({ k, v, t }: { k: string; v: string | null | undefined; t?: { notSet: string } }) {
  return (
    <p>
      <strong>{k}:</strong> {v ?? t?.notSet ?? "—"}
    </p>
  );
}
