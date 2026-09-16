/**
 * Add Crop screen (auth-only): catalogue-assisted, variety optional.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import {
  CropForm,
  EMPTY_CROP,
  toCropWrite,
  type CropFormValues,
} from "../../../../../components/CropForm";
import { ApiError, api, getStoredToken, type CropVariety } from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";

export default function NewCropPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<CropFormValues>(EMPTY_CROP);
  const [varieties, setVarieties] = useState<CropVariety[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    api.listVarieties(token).then(setVarieties).catch(() => {
      /* catalogue is a helper — the form works without it */
    });
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
      const crop = await api.createCrop(token, params.id, toCropWrite(values));
      router.push(`/farms/${params.id}/crops/${crop.id}`);
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
          <h1>🌱 {t.addCrop}</h1>
          <CropForm
            t={t}
            values={values}
            onChange={setValues}
            onSubmit={onSubmit}
            busy={busy}
            error={error}
            submitLabel={busy ? t.saving : t.save}
            varieties={varieties}
          />
          <p>
            <Link href={`/farms/${params.id}/crops`}>← {t.backToFarms}</Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
