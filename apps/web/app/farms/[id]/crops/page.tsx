/**
 * Farm Crops List (auth-only): plantings on one farm + add button.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { seasonLabel, statusLabel } from "../../../../components/cropLabels";
import { ApiError, api, getStoredToken, type Crop } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";

export default function FarmCropsPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [crops, setCrops] = useState<Crop[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setCrops(await api.listCrops(token, params.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}`}>← {t.backToFarms}</Link>
        </p>
        <div className="page-head">
          <h1>🌱 {t.myCrops}</h1>
          <Link className="btn add-btn" href={`/farms/${params.id}/crops/new`}>
            + {t.addCrop}
          </Link>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        {crops === null ? (
          <p className="muted">{t.loading}</p>
        ) : crops.length === 0 ? (
          <section className="card">
            <h2>{t.noCrops}</h2>
            <p className="muted">{t.noCropsHint}</p>
            <Link className="btn" href={`/farms/${params.id}/crops/new`}>
              + {t.addCrop}
            </Link>
          </section>
        ) : (
          <div className="grid">
            {crops.map((c) => (
              <article className="card farm-card" key={c.id}>
                <h2>{c.crop_name}</h2>
                {c.variety_name ? <p className="muted">{c.variety_name}</p> : null}
                <p className="farm-area">
                  {c.area} {c.area_unit}
                </p>
                <p className="muted">
                  {seasonLabel(t, c.season)} · {t.sowingDate}: {c.sowing_date}
                </p>
                <p className="muted">
                  {t.statusLabel}: {statusLabel(t, c.status)}
                </p>
                <div className="card-actions">
                  <Link
                    className="btn-secondary link-btn"
                    href={`/farms/${params.id}/crops/${c.id}`}
                  >
                    {t.viewDetails}
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
