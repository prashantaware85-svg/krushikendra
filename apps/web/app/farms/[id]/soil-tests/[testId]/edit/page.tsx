/**
 * Edit Soil Test screen (auth-only).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../components/AuthGate";
import {
  EMPTY_SOIL_TEST,
  SoilTestForm,
  toSoilTestWrite,
  type SoilFormValues,
} from "../../../../../../components/SoilTestForm";
import { ApiError, api, getStoredToken } from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";

const STR_KEYS = [
  "laboratory_name",
  "report_number",
  "soil_type",
  "notes",
] as const;

const NUM_KEYS = [
  "ph",
  "electrical_conductivity",
  "organic_carbon",
  "nitrogen",
  "phosphorus",
  "potassium",
  "sulphur",
  "zinc",
  "iron",
  "manganese",
  "copper",
  "boron",
] as const;

export default function EditSoilTestPage({
  params,
}: {
  params: { id: string; testId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<SoilFormValues | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const s = await api.getSoilTest(token, params.id, params.testId);
      const next: SoilFormValues = { ...EMPTY_SOIL_TEST, test_date: s.test_date };
      for (const k of STR_KEYS) next[k] = (s[k] as string | null) ?? "";
      for (const k of NUM_KEYS) next[k] = (s[k] as string | null) ?? "";
      setValues(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.testId]);

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
      await api.updateSoilTest(token, params.id, params.testId, toSoilTestWrite(values));
      router.push(`/farms/${params.id}/soil-tests/${params.testId}`);
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
          <h1>🧪 {t.editSoilTest}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <SoilTestForm
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
            <Link href={`/farms/${params.id}/soil-tests/${params.testId}`}>
              ← {t.soilHistory}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
