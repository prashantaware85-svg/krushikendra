/**
 * Crop Health timeline (auth-only): chronological observations.
 * Tracking only — records are never diagnoses.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../components/AuthGate";
import {
  observationStatusLabel,
  observationTypeLabel,
  severityDot,
  severityLabel,
} from "../../../../../../components/healthLabels";
import { ApiError, api, getStoredToken, type HealthObservation } from "../../../../../../lib/api";
import { useAuth } from "../../../../../../lib/auth";

export default function HealthTimelinePage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const [items, setItems] = useState<HealthObservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setItems(await api.listObservations(token, params.id, params.cropId));
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
          <div>
            <h1>🐛 {t.healthTitle}</h1>
            <p className="muted">{t.healthHint}</p>
          </div>
          <Link
            className="btn add-btn"
            href={`/farms/${params.id}/crops/${params.cropId}/health/new`}
          >
            + {t.addObservation}
          </Link>
        </div>
        {error ? <p className="form-error">{error}</p> : null}
        {items === null ? (
          <p className="muted">{t.loading}</p>
        ) : items.length === 0 ? (
          <section className="card">
            <p className="muted">{t.noObservations}</p>
            <p className="muted">{t.noObservationsHint}</p>
          </section>
        ) : (
          <div className="timeline">
            {items.map((o) => (
              <p key={o.id} className="tl-row">
                <span>{severityDot(o.severity)}</span>{" "}
                <strong>{displayName(o)}</strong>
                <br />
                <span className="muted">
                  {o.observation_date} · {observationTypeLabel(t, o.observation_type)} ·{" "}
                  {t.severityLabel}: {severityLabel(t, o.severity)} · {t.obsStatus}:{" "}
                  {observationStatusLabel(t, o.status)}{" "}
                </span>
                <Link href={`/farms/${params.id}/crops/${params.cropId}/health/${o.id}`}>
                  [{t.viewDetails}]
                </Link>
              </p>
            ))}
          </div>
        )}
      </main>
    </AuthGate>
  );
}

function displayName(o: HealthObservation): string {
  return o.observed_name ?? o.pest_name ?? o.disease_name ?? o.observation_type;
}
