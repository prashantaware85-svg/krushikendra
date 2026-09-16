/**
 * Edit Crop screen (auth-only): loads the crop, saves partial updates.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../components/AuthGate";
import {
  CropForm,
  EMPTY_CROP,
  toCropWrite,
  type CropFormValues,
} from "../../../../../../components/CropForm";
import {
  ApiError,
  api,
  getStoredToken,
  type CropVariety,
} from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";

export default function EditCropPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<CropFormValues | null>(null);
  const [varieties, setVarieties] = useState<CropVariety[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [c, v] = await Promise.all([
        api.getCrop(token, params.id, params.cropId),
        api.listVarieties(token).catch(() => [] as CropVariety[]),
      ]);
      setVarieties(v);
      setValues({
        ...EMPTY_CROP,
        crop_name: c.crop_name,
        variety_name: c.variety_name ?? "",
        crop_variety_id: c.crop_variety_id,
        area: c.area,
        area_unit: c.area_unit,
        season: c.season,
        sowing_date: c.sowing_date,
        expected_harvest_date: c.expected_harvest_date ?? "",
        status: c.status,
        notes: c.notes ?? "",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId]);

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
      await api.updateCrop(token, params.id, params.cropId, toCropWrite(values));
      router.push(`/farms/${params.id}/crops/${params.cropId}`);
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
          <h1>🌱 {t.editCrop}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
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
          )}
          <p>
            <Link href={`/farms/${params.id}/crops/${params.cropId}`}>
              ← {t.backToFarms}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
