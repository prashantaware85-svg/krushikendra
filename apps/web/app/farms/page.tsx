/**
 * My Farms list (auth-only): farm cards + add/edit/view/delete.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../components/AuthGate";
import { ApiError, api, getStoredToken, type Farm } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function FarmsPage() {
  const { t } = useAuth();
  const router = useRouter();
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setFarms(await api.listFarms(token));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onDelete(id: string) {
    if (!window.confirm(t.deleteConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteFarm(token, id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <div className="page-head">
          <div>
            <h1>🌾 {t.myFarms}</h1>
            <p className="muted">{t.myFarmsHint}</p>
          </div>
          <Link className="btn add-btn" href="/farms/new">
            + {t.addFarm}
          </Link>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        {farms === null ? (
          <p className="muted">{t.loading}</p>
        ) : farms.length === 0 ? (
          <section className="card">
            <h2>{t.noFarms}</h2>
            <p className="muted">{t.noFarmsHint}</p>
            <Link className="btn" href="/farms/new">
              + {t.addFarm}
            </Link>
          </section>
        ) : (
          <div className="grid">
            {farms.map((f) => (
              <article className="card farm-card" key={f.id}>
                <h2>{f.farm_name}</h2>
                <p className="farm-area">
                  {f.area} {unitLabel(t, f.area_unit)}
                </p>
                <p className="muted">
                  {t.villageLabel}: {f.village ?? t.notSet}
                </p>
                <p className="muted">
                  {t.soilType}: {f.soil_type ?? t.notSet} · {t.irrigation}:{" "}
                  {irrigationLabel(t, f.irrigation_type)}
                </p>
                <div className="card-actions">
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => router.push(`/farms/${f.id}`)}
                  >
                    {t.viewDetails}
                  </button>
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => router.push(`/farms/${f.id}/edit`)}
                  >
                    {t.edit}
                  </button>
                  <button
                    className="btn-danger"
                    type="button"
                    onClick={() => onDelete(f.id)}
                  >
                    {t.deleteFarm}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}

function unitLabel(t: { acre: string; hectare: string; guntha: string }, u: string) {
  if (u === "hectare") return t.hectare;
  if (u === "guntha") return t.guntha;
  return t.acre;
}

function irrigationLabel(t: Record<string, string>, v: string | null) {
  const map: Record<string, string> = {
    rainfed: t.irrigationRainfed,
    drip: t.irrigationDrip,
    sprinkler: t.irrigationSprinkler,
    flood: t.irrigationFlood,
    mixed: t.irrigationMixed,
    other: t.irrigationOther,
  };
  return (v && map[v]) || t.notSet;
}

