/**
 * Fertilizer History (auth-only): usage records for one crop, newest first.
 * Usage records only — never advice.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Fertilizer } from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";

export default function FertilizerHistoryPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const [items, setItems] = useState<Fertilizer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setItems(await api.listFertilizers(token, params.id, params.cropId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}/crops/${params.cropId}`}>
            ← {t.backToCrop}
          </Link>
        </p>
        <div className="page-head">
          <h1>🧪 {t.fertilizerHistory}</h1>
          <Link
            className="btn add-btn"
            href={`/farms/${params.id}/crops/${params.cropId}/fertilizers/new`}
          >
            + {t.addFertilizer}
          </Link>
        </div>
        {error ? <p className="form-error">{error}</p> : null}
        {items === null ? (
          <p className="muted">{t.loading}</p>
        ) : items.length === 0 ? (
          <section className="card">
            <p className="muted">{t.noFertilizers}</p>
            <p className="muted">{t.noFertilizersHint}</p>
          </section>
        ) : (
          <div className="grid">
            {items.map((f) => (
              <article className="card" key={f.id}>
                <h2>{f.fertilizer_name}</h2>
                <p className="farm-area">
                  {f.quantity} {f.quantity_unit}
                </p>
                <p className="muted">{f.application_date}</p>
                <p>
                  <Link
                    href={`/farms/${params.id}/crops/${params.cropId}/fertilizers/${f.id}`}
                  >
                    [{t.viewDetails}]
                  </Link>
                </p>
              </article>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}
