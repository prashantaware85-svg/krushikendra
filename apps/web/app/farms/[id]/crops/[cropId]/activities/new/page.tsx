/**
 * Add Activity screen (auth-only): manual record, defaults to planned.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { activityStatusLabel, activityTypeLabel } from "../../../../../../../components/activityLabels";
import {
  ActivityForm,
  EMPTY_ACTIVITY,
  toActivityWrite,
  type ActivityFormValues,
} from "../../../../../../../components/ActivityForm";
import { AuthGate } from "../../../../../../../components/AuthGate";
import { ApiError, api, getStoredToken } from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function NewActivityPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<ActivityFormValues>(EMPTY_ACTIVITY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    const token = getStoredToken();
    if (!token) {
      setError("Session missing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const act = await api.createActivity(
        token,
        params.id,
        params.cropId,
        toActivityWrite(values),
      );
      router.push(`/farms/${params.id}/crops/${params.cropId}/activities/${act.id}`);
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
          <h1>📝 {t.addActivity}</h1>
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
          <p>
            <Link href={`/farms/${params.id}/crops/${params.cropId}/activities`}>
              ← {t.backToCrop}
            </Link>
          </p>
        </section>
      </main>
    </AuthGate>
  );
}
