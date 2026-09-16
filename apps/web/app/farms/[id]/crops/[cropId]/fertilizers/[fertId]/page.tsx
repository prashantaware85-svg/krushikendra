/**
 * Fertilizer Details (auth-only): one usage record. Display only.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken, type Fertilizer } from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function FertilizerPage({
  params,
}: {
  params: { id: string; cropId: string; fertId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [item, setItem] = useState<Fertilizer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      setItem(await api.getFertilizer(token, params.id, params.cropId, params.fertId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.fertId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onDelete() {
    if (!window.confirm(t.deleteFertilizerConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteFertilizer(token, params.id, params.cropId, params.fertId);
      router.push(`/farms/${params.id}/crops/${params.cropId}/fertilizers`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/farms/${params.id}/crops/${params.cropId}/fertilizers`}>
            ← {t.fertilizerHistory}
          </Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!item ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <section className="card">
            <h1>
              🧪 {item.fertilizer_name}
            </h1>
            <KV k={t.fertilizerType} v={item.fertilizer_type} t={t} />
            <KV k={t.fertQuantity} v={`${item.quantity} ${item.quantity_unit}`} />
            <KV k={t.applicationDate} v={item.application_date} />
            <KV k={t.applicationMethod} v={item.application_method} t={t} />
            <KV k={t.purposeLabel} v={item.purpose} t={t} />
            <KV k={t.soilNotes} v={item.notes} t={t} />
            <div className="card-actions">
              <button
                className="btn-secondary"
                type="button"
                onClick={() =>
                  router.push(
                    `/farms/${params.id}/crops/${params.cropId}/fertilizers/${params.fertId}/edit`,
                  )
                }
              >
                {t.edit}
              </button>
              <button className="btn-danger" type="button" onClick={onDelete}>
                {t.deleteFertilizer}
              </button>
            </div>
          </section>
        )}
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
