/**
 * Edit Farm screen (auth-only): loads the farm, saves partial updates.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import {
  EMPTY_FARM,
  FarmForm,
  toFarmWrite,
  type FarmFormValues,
} from "../../../../components/FarmForm";
import { ApiError, api, getStoredToken, type AreaUnit } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";

export default function EditFarmPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<FarmFormValues | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const f = await api.getFarm(token, params.id);
      setValues({
        ...EMPTY_FARM,
        farm_name: f.farm_name,
        area: f.area,
        area_unit: f.area_unit as AreaUnit,
        state: f.state ?? "",
        district: f.district ?? "",
        taluka: f.taluka ?? "",
        village: f.village ?? "",
        latitude: f.latitude ?? "",
        longitude: f.longitude ?? "",
        land_type: f.land_type ?? "",
        soil_type: f.soil_type ?? "",
        irrigation_type: f.irrigation_type ?? "",
        water_source: f.water_source ?? "",
        ownership_type: f.ownership_type ?? "",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
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
      await api.updateFarm(token, params.id, toFarmWrite(values));
      router.push(`/farms/${params.id}`);
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
          <h1>🌾 {t.editFarm}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <FarmForm
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
            <Link href={`/farms/${params.id}`}>← {t.backToFarms}</Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
