/**
 * Crop Problem Check (auth-only): farm → crop → 1-3 photos → analyze,
 * plus "My Crop Images" history. Display only — no treatment decisions.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type AnalysisHistoryItem,
  type Crop,
  type Farm,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function CropCheckPage() {
  const { t, language } = useAuth();
  const router = useRouter();
  const [farms, setFarms] = useState<Farm[]>([]);
  const [farmId, setFarmId] = useState("");
  const [crops, setCrops] = useState<Crop[]>([]);
  const [cropId, setCropId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [history, setHistory] = useState<AnalysisHistoryItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [farmList, items] = await Promise.all([
        api.listFarms(token).catch(() => [] as Farm[]),
        api.listAnalyses(token).catch(() => [] as AnalysisHistoryItem[]),
      ]);
      setFarms(farmList);
      setHistory(items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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

  // Local object-URL previews (photos stay on-device until Analyze).
  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  function pick(selected: FileList | null) {
    if (!selected) return;
    setFiles(Array.from(selected).slice(0, 3));
  }

  async function onAnalyze() {
    const token = getStoredToken();
    if (!token || !farmId || !cropId || files.length === 0 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadCropImages(token, {
        farm_id: farmId,
        crop_id: cropId,
        language,
        files,
      });
      router.push(`/crop-check/${result.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t.deleteAnalysisConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteAnalysis(token, id);
      setHistory((prev) => (prev ? prev.filter((h) => h.id !== id) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <h1>📸 {t.cropCheckTitle}</h1>
        <p className="muted">{t.cropCheckHint}</p>

        <section className="card">
          <label className="field">
            <span>{t.aiFarmLabel}</span>
            <select value={farmId} onChange={(e) => setFarmId(e.target.value)}>
              <option value="">—</option>
              {farms.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.farm_name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t.aiCropLabel}</span>
            <select
              value={cropId}
              onChange={(e) => setCropId(e.target.value)}
              disabled={!farmId}
            >
              <option value="">{t.aiAnyCrop}</option>
              {crops.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.crop_name}
                </option>
              ))}
            </select>
          </label>

          <div className="card-actions">
            <label className="btn-secondary link-btn" htmlFor="crop-photo-capture">
              📷 {t.takePhoto}
            </label>
            <label className="btn-secondary link-btn" htmlFor="crop-photo-pick">
              🖼️ {t.uploadPhoto}
            </label>
          </div>
          <input
            id="crop-photo-capture"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            multiple
            hidden
            onChange={(e) => pick(e.target.files)}
          />
          <input
            id="crop-photo-pick"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            hidden
            onChange={(e) => pick(e.target.files)}
          />

          {previews.length > 0 ? (
            <>
              <p className="muted">{t.selectedImages}</p>
              <div className="preview-row">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {previews.map((src, i) => (
                  <img key={i} src={src} alt="" className="preview-img" />
                ))}
              </div>
            </>
          ) : null}
          <p className="muted small">{t.maxImagesNote}</p>

          {error ? <p className="form-error">{error}</p> : null}
          <button
            className="btn"
            type="button"
            disabled={busy || !farmId || !cropId || files.length === 0}
            onClick={onAnalyze}
          >
            {busy ? t.analyzing : t.analyze}
          </button>
        </section>

        <section className="card">
          <h2>🖼️ {t.myAnalyses}</h2>
          {history === null ? (
            <p className="muted">{t.loading}</p>
          ) : history.length === 0 ? (
            <>
              <p className="muted">{t.noAnalyses}</p>
              <p className="muted">{t.noAnalysesHint}</p>
            </>
          ) : (
            history.map((h) => (
              <p key={h.id}>
                <strong>{h.possible_condition ?? h.status}</strong> ·{" "}
                {h.crop_name ?? ""} · {h.created_at.slice(0, 10)} ·{" "}
                <Link href={`/crop-check/${h.id}`}>[{t.openAnalysis}]</Link>{" "}
                <button
                  type="button"
                  className="link-btn-plain"
                  onClick={() => onDelete(h.id)}
                >
                  [{t.deleteAnalysis}]
                </button>
              </p>
            ))
          )}
        </section>
      </main>
    </AuthGate>
  );
}
