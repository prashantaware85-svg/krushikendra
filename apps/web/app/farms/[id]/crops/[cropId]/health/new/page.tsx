/**
 * Add Health Observation screen (auth-only): free text always allowed,
 * catalogue pickers optional. Records only — never a diagnosis.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGate } from "../../../../../../../components/AuthGate";
import {
  EMPTY_OBSERVATION,
  HealthForm,
  toObservationWrite,
  type HealthFormValues,
} from "../../../../../../../components/HealthForm";
import {
  ApiError,
  api,
  getStoredToken,
  type PestDisease,
} from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function NewObservationPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<HealthFormValues>(EMPTY_OBSERVATION);
  const [pests, setPests] = useState<PestDisease[]>([]);
  const [diseases, setDiseases] = useState<PestDisease[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    api.listPests(token).then(setPests).catch(() => setPests([]));
    api.listDiseases(token).then(setDiseases).catch(() => setDiseases([]));
  }, []);

  async function onSubmit() {
    const token = getStoredToken();
    if (!token) {
      setError("Session missing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createObservation(
        token,
        params.id,
        params.cropId,
        toObservationWrite(values),
      );
      router.push(`/farms/${params.id}/crops/${params.cropId}/health/${created.id}`);
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
          <h1>🐛 {t.addObservation}</h1>
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
          <p>
            <Link href={`/farms/${params.id}/crops/${params.cropId}/health`}>
              ← {t.backToHealth}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
