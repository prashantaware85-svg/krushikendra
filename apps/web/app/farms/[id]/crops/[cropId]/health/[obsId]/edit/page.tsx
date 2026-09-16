/**
 * Edit Health Observation screen (auth-only).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../../../components/AuthGate";
import {
  EMPTY_OBSERVATION,
  HealthForm,
  toObservationWrite,
  type HealthFormValues,
} from "../../../../../../../../components/HealthForm";
import {
  ApiError,
  api,
  getStoredToken,
  type PestDisease,
} from "../../../../../../../../lib/api";
import { useAuth } from "../../../../../../../../lib/auth";

export default function EditObservationPage({
  params,
}: {
  params: { id: string; cropId: string; obsId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<HealthFormValues | null>(null);
  const [pests, setPests] = useState<PestDisease[]>([]);
  const [diseases, setDiseases] = useState<PestDisease[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [o, p, d] = await Promise.all([
        api.getObservation(token, params.id, params.cropId, params.obsId),
        api.listPests(token).catch(() => [] as PestDisease[]),
        api.listDiseases(token).catch(() => [] as PestDisease[]),
      ]);
      setPests(p);
      setDiseases(d);
      setValues({
        ...EMPTY_OBSERVATION,
        observation_type: o.observation_type,
        pest_id: o.pest_id ?? "",
        disease_id: o.disease_id ?? "",
        observed_name: o.observed_name ?? "",
        observation_date: o.observation_date,
        severity: o.severity,
        affected_area: o.affected_area ?? "",
        affected_area_unit: o.affected_area_unit ?? "",
        symptoms: o.symptoms ?? "",
        notes: o.notes ?? "",
        status: o.status,
        source: o.source,
        linked_image_analysis_id: "",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.obsId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onSubmit() {
    if (!values) return;
    const token = getStoredToken();
    if (!token) {
      setError("Session missing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateObservation(
        token,
        params.id,
        params.cropId,
        params.obsId,
        toObservationWrite(values),
      );
      router.push(`/farms/${params.id}/crops/${params.cropId}/health/${params.obsId}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <section className="card">
          <h1>🐛 {t.editObservation}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <HealthForm
              t={t}
              values={values}
              onChange={setValues}
              onSubmit={onSubmit}
              busy={busy}
              error={error}
              submitLabel={busy ? t.saving : t.save}
              pests={pests}
              diseases={diseases}
            />
          )}
          <p>
            <Link
              href={`/farms/${params.id}/crops/${params.cropId}/health/${params.obsId}`}
            >
              ← {t.backToHealth}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
