/**
 * Edit Activity screen (auth-only).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { activityStatusLabel, activityTypeLabel } from "../../../../../../../../components/activityLabels";
import {
  ActivityForm,
  EMPTY_ACTIVITY,
  toActivityWrite,
  type ActivityFormValues,
} from "../../../../../../../../components/ActivityForm";
import { AuthGate } from "../../../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken } from "../../../../../../../../lib/api";
import { useAuth } from "../../../../../../../../lib/auth";

export default function EditActivityPage({
  params,
}: {
  params: { id: string; cropId: string; activityId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<ActivityFormValues | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const a = await api.getActivity(token, params.id, params.cropId, params.activityId);
      setValues({
        ...EMPTY_ACTIVITY,
        activity_type: a.activity_type,
        title: a.title,
        description: a.description ?? "",
        activity_date: a.activity_date,
        status: a.status,
        quantity: a.quantity ?? "",
        quantity_unit: a.quantity_unit ?? "",
        cost: a.cost ?? "",
        notes: a.notes ?? "",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.activityId]);

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
      await api.updateActivity(
        token,
        params.id,
        params.cropId,
        params.activityId,
        toActivityWrite(values),
      );
      router.push(
        `/farms/${params.id}/crops/${params.cropId}/activities/${params.activityId}`,
      );
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
          <h1>📝 {t.editActivity}</h1>
          {!values ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <ActivityForm
              t={t}
              values={values}
              onChange={setValues}
              onSubmit={onSubmit}
              busy={busy}
              error={error}
              submitLabel={busy ? t.saving : t.save}
              typeLabel={(v) => activityTypeLabel(t, v)}
              statusLabelFn={(v) => activityStatusLabel(t, v)}
            />
          )}
          <p>
            <Link
              href={`/farms/${params.id}/crops/${params.cropId}/activities/${params.activityId}`}
            >
              ← {t.backToCrop}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
