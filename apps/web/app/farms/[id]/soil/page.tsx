/**
 * Soil Information screen (auth-only): view the farm's soil record.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Soil } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";

export default function SoilPage({ params }: { params: { id: string } }) {
  const { t } = useAuth();
  const [soil, setSoil] = useState<Soil | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setSoil(await api.getSoil(token, params.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setSoil(null);
      else setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/farms/${params.id}`}>← {t.backToFarms}</Link>
        </p>
        <section className="card">
          <h1>🧪 {t.soilInfo}</h1>
          {error ? <p className="form-error">{error}</p> : null}
          {soil === undefined ? (
            <p className="muted">{t.loading}</p>
          ) : soil === null ? (
            <>
              <p className="muted">{t.noSoil}</p>
              <Link className="btn" href={`/farms/${params.id}/soil/edit`}>
                {t.addSoil}
              </Link>
            </>
          ) : (
            <>
              <KV k={t.soilType} v={soil.soil_type} t={t} />
              <KV k={t.soilTestAvailable} v={soil.soil_test_available ? t.yes : t.no} />
              <KV k={t.soilTestDate} v={soil.soil_test_date} t={t} />
              <KV k={t.phLabel} v={soil.ph} t={t} />
              <KV k={t.organicCarbon} v={soil.organic_carbon} t={t} />
              <KV k={t.nitrogen} v={soil.nitrogen} t={t} />
              <KV k={t.phosphorus} v={soil.phosphorus} t={t} />
              <KV k={t.potassium} v={soil.potassium} t={t} />
              <KV k={t.docRef} v={soil.soil_test_document_reference} t={t} />
              <p>
                <Link href={`/farms/${params.id}/soil/edit`}>{t.editSoil}</Link>
              </p>
            </>
          )}
        </section>
      </main>
    </AuthGate>
  );
}

function KV({ k, v, t }: { k: string; v: string | null | undefined; t?: { notSet: string } }) {
  return (
    <p>
      <strong>{k}:</strong> {v ?? t?.notSet ?? "—"}
    </p>
  );
}
