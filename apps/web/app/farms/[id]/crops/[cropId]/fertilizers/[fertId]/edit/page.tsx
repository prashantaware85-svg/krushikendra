/**
 * Edit Fertilizer Application screen (auth-only).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../../../components/AuthGate";
import {
  EMPTY_FERTILIZER,
  FertilizerForm,
  toFertilizerWrite,
  type FertilizerFormValues,
} from "../../../../../../../../components/FertilizerForm";
import { ApiError, api, getStoredToken } from "../../../../../../../../lib/api";
import { useAuth } from "../../../../../../../../lib/auth";

export default function EditFertilizerPage({
  params,
}: {
  params: { id: string; cropId: string; fertId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<FertilizerFormValues | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const f = await api.getFertilizer(token, params.id, params.cropId, params.fertId);
      setValues({
        ...EMPTY_FERTILIZER,
        fertilizer_name: f.fertilizer_name,
        fertilizer_type: f.fertilizer_type ?? "",
        quantity: f.quantity,
        quantity_unit: f.quantity_unit,
        application_date: f.application_date,
        application_method: f.application_method ?? "",
        purpose: f.purpose ?? "",
        notes: f.notes ?? "",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.fertId]);

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
      await api.updateFertilizer(
        token,
        params.id,
        params.cropId,
        params.fertId,
        toFertilizerWrite(values),
      );
      router.push(`/farms/${params.id}/crops/${params.cropId}/fertilizers/${params.fertId}`);
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
          <h1>🧪 {t.editFertilizer}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <FertilizerForm
              t={t}
              values={values}
              onChange={setValues}
              onSubmit={onSubmit}
              busy={busy}
              error={error}
              submitLabel={busy ? t.saving : t.save}
            />
          )}
          <p>
            <Link
              href={`/farms/${params.id}/crops/${params.cropId}/fertilizers/${params.fertId}`}
            >
              ← {t.fertilizerHistory}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
