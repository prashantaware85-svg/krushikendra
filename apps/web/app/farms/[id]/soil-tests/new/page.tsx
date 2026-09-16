/**
 * Add Soil Test screen (auth-only): values as reported, all but date optional.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import {
  EMPTY_SOIL_TEST,
  SoilTestForm,
  toSoilTestWrite,
  type SoilFormValues,
} from "../../../../../components/SoilTestForm";
import { ApiError, api, getStoredToken } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";

export default function NewSoilTestPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<SoilFormValues>(EMPTY_SOIL_TEST);
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
      const created = await api.createSoilTest(token, params.id, toSoilTestWrite(values));
      router.push(`/farms/${params.id}/soil-tests/${created.id}`);
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
          <h1>🧪 {t.addSoilTest}</h1>
          <SoilTestForm
            t={t}
            values={values}
            onChange={setValues}
            onSubmit={onSubmit}
            busy={busy}
            error={error}
            submitLabel={busy ? t.saving : t.save}
          />
          <p>
            <Link href={`/farms/${params.id}/soil-tests`}>← {t.soilHistory}</Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
