/**
 * Add Farm screen (auth-only).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthGate } from "../../../components/AuthGate";
import {
  EMPTY_FARM,
  FarmForm,
  toFarmWrite,
  type FarmFormValues,
} from "../../../components/FarmForm";
import { ApiError, api, getStoredToken } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";

export default function NewFarmPage() {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<FarmFormValues>(EMPTY_FARM);
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
      const farm = await api.createFarm(token, toFarmWrite(values));
      router.push(`/farms/${farm.id}`);
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
          <h1>🌾 {t.addFarm}</h1>
          <FarmForm
            t={t}
            values={values}
            onChange={setValues}
            onSubmit={onSubmit}
            busy={busy}
            error={error}
            submitLabel={busy ? t.saving : t.save}
          />
          <p>
            <Link href="/farms">← {t.backToFarms}</Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
