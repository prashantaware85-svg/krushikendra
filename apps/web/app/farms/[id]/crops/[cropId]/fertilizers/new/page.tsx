/**
 * Add Fertilizer Application screen (auth-only): records usage ("used X").
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthGate } from "../../../../../../../components/AuthGate";
import {
  EMPTY_FERTILIZER,
  FertilizerForm,
  toFertilizerWrite,
  type FertilizerFormValues,
} from "../../../../../../../components/FertilizerForm";
import { ApiError, api, getStoredToken } from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function NewFertilizerPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<FertilizerFormValues>(EMPTY_FERTILIZER);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    const token = getStoredToken();
    if (!token) {
      setError("Session missing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createFertilizer(
        token,
        params.id,
        params.cropId,
        toFertilizerWrite(values),
      );
      router.push(`/farms/${params.id}/crops/${params.cropId}/fertilizers/${created.id}`);
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
          <h1>🧪 {t.addFertilizer}</h1>
          <FertilizerForm
            t={t}
            values={values}
            onChange={setValues}
            onSubmit={onSubmit}
            busy={busy}
            error={error}
            submitLabel={busy ? t.saving : t.save}
          />
          <p>
            <Link href={`/farms/${params.id}/crops/${params.cropId}/fertilizers`}>
              ← {t.fertilizerHistory}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
