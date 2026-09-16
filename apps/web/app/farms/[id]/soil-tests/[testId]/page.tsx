/**
 * Soil Test Details (auth-only): values + lab info + report view/download.
 * Display only — no recommendations.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type SoilTest } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";

export default function SoilTestPage({ params }: { params: { id: string; testId: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [test, setTest] = useState<SoilTest | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setTest(await api.getSoilTest(token, params.id, params.testId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.testId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onReport(file: File | undefined) {
    if (!file) return;
    const token = getStoredToken();
    if (!token) return;
    setUploading(true);
    setError(null);
    try {
      setTest(await api.uploadSoilReport(token, params.id, params.testId, file));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setUploading(false);
    }
  }

  async function downloadReport() {
    const token = getStoredToken();
    if (!token) return;
    try {
      const blob = await api.soilReportBlob(token, params.id, params.testId);
      const url = URL.createObjectURL(blob.blob);
      setReportUrl(url);
      window.open(url, "_blank", "noopener");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  async function onDelete() {
    if (!window.confirm(t.deleteSoilTestConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteSoilTest(token, params.id, params.testId);
      router.push(`/farms/${params.id}/soil-tests`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/farms/${params.id}/soil-tests`}>← {t.soilHistory}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!test ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <section className="card">
            <h1>
              🧪 {test.test_date}
            </h1>
            <KV k={t.labName} v={test.laboratory_name} t={t} />
            <KV k={t.reportNumber} v={test.report_number} t={t} />
            <KV k={t.soilType} v={test.soil_type} t={t} />
            <KV k="pH" v={test.ph} />
            <KV k={t.ecLabel} v={test.electrical_conductivity} />
            <KV k={t.organicCarbonLabel} v={test.organic_carbon} />
            <KV k={t.nitrogenLabel} v={test.nitrogen} />
            <KV k={t.phosphorusLabel} v={test.phosphorus} />
            <KV k={t.potassiumLabel} v={test.potassium} />
            <KV k={t.sulphurLabel} v={test.sulphur} />
            <KV k={t.zincLabel} v={test.zinc} />
            <KV k={t.ironLabel} v={test.iron} />
            <KV k={t.manganeseLabel} v={test.manganese} />
            <KV k={t.copperLabel} v={test.copper} />
            <KV k={t.boronLabel} v={test.boron} />
            {test.notes ? <KV k={t.soilNotes} v={test.notes} /> : null}
            <p>
              <strong>{t.reportUpload}:</strong>{" "}
              {test.has_report ? t.hasReport : t.noReport}
            </p>
            {test.has_report ? (
              <p>
                <button
                  className="btn-secondary"
                  type="button"
                  onClick={downloadReport}
                >
                  {t.viewReport}
                </button>
              </p>
            ) : null}
            <label className="field">
              <span>{t.reportUpload} ({t.optional})</span>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                disabled={uploading}
                onChange={(e) => onReport(e.target.files?.[0])}
              />
            </label>
            <div className="card-actions">
              <button
                className="btn-secondary"
                type="button"
                onClick={() =>
                  router.push(`/farms/${params.id}/soil-tests/${params.testId}/edit`)
                }
              >
                {t.edit}
              </button>
              <button className="btn-danger" type="button" onClick={onDelete}>
                {t.deleteSoilTest}
              </button>
            </div>
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
