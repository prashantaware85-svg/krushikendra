/**
 * Edit Soil screen (auth-only): creates the record if absent, else updates.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import {
  EMPTY_SOIL,
  SoilForm,
  toSoilWrite,
  type SoilFormValues,
} from "../../../../../components/SoilForm";
import { ApiError, api, getStoredToken } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";

export default function EditSoilPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<SoilFormValues | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const s = await api.getSoil(token, params.id);
      setValues({
        ...EMPTY_SOIL,
        soil_type: s.soil_type ?? "",
        soil_test_available: s.soil_test_available,
        soil_test_date: s.soil_test_date ?? "",
        ph: s.ph ?? "",
        organic_carbon: s.organic_carbon ?? "",
        nitrogen: s.nitrogen ?? "",
        phosphorus: s.phosphorus ?? "",
        potassium: s.potassium ?? "",
        soil_test_document_reference: s.soil_test_document_reference ?? "",
      });
      setIsNew(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setValues(EMPTY_SOIL);
        setIsNew(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Error");
      }
    }
  }, [params.id]);

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
      if (isNew) await api.createSoil(token, params.id, toSoilWrite(values));
      else await api.updateSoil(token, params.id, toSoilWrite(values));
      router.push(`/farms/${params.id}/soil`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/farms/${params.id}/soil`}>← {t.backToFarms}</Link>
        </p>
        <section className="card">
          <h1>🧪 {isNew ? t.addSoil : t.editSoil}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <SoilForm
              t={t}
              values={values}
              onChange={setValues}
              onSubmit={onSubmit}
              busy={busy}
              error={error}
              submitLabel={busy ? t.saving : t.save}
            />
          )}
        </section>
      </main>
    </AuthGate>
  );
}
