/**
 * Activity Details (auth-only): activity + crop + farm context, with
 * Edit / Mark completed / Delete actions. Display only — no advice.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { activityStatusLabel, activityTypeLabel } from "../../../../../../../components/activityLabels";
import { AuthGate } from "../../../../../../../components/AuthGate";
import {
  ApiError,
  api,
  getStoredToken,
  type Activity,
  type Crop,
  type Farm,
} from "../../../../../../../lib/api";
import { useAuth } from "../../../../../../../lib/auth";

export default function ActivityDetailsPage({
  params,
}: {
  params: { id: string; cropId: string; activityId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [activity, setActivity] = useState<Activity | null>(null);
  const [crop, setCrop] = useState<Crop | null>(null);
  const [farm, setFarm] = useState<Farm | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [a, c, f] = await Promise.all([
        api.getActivity(token, params.id, params.cropId, params.activityId),
        api.getCrop(token, params.id, params.cropId),
        api.getFarm(token, params.id),
      ]);
      setActivity(a);
      setCrop(c);
      setFarm(f);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }, [params.id, params.cropId, params.activityId]);

  useEffect(() => {
    load();
  }, [load]);

  async function markCompleted() {
    const token = getStoredToken();
    if (!token || !activity) return;
    setBusy(true);
    try {
      setActivity(
        await api.updateActivity(token, params.id, params.cropId, activity.id, {
          status: "completed",
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!window.confirm(t.deleteActivityConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteActivity(token, params.id, params.cropId, params.activityId);
      router.push(`/farms/${params.id}/crops/${params.cropId}/activities`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main auth-wrap">
        <p>
          <Link href={`/farms/${params.id}/crops/${params.cropId}/activities`}>
            ← {t.backToCrop}
          </Link>
        </p>
        <section className="card">
          {!activity ? (
            <p className="muted">{error ?? t.loading}</p>
          ) : (
            <>
              <h1>
                {activity.status === "completed" ? "✓ " : "○ "}
                {activity.title}
              </h1>
              <KV k={t.activityType} v={activityTypeLabel(t, activity.activity_type)} />
              <KV k={t.cropName} v={crop?.crop_name} />
              <KV k={t.farmName} v={farm?.farm_name} />
              <KV k={t.activityDate} v={activity.activity_date} />
              <KV k={t.statusLabel} v={activityStatusLabel(t, activity.status)} />
              <KV
                k={t.quantity}
                v={
                  activity.quantity
                    ? `${activity.quantity} ${activity.quantity_unit ?? ""}`.trim()
                    : null
                }
                t={t}
              />
              <KV k={t.cost} v={activity.cost ? `₹ ${activity.cost}` : null} t={t} />
              <KV k={t.description} v={activity.description} t={t} />
              <KV k={t.notes} v={activity.notes} t={t} />
              <KV k={t.createdOn} v={activity.created_at.slice(0, 10)} />
              {error ? <p className="form-error">{error}</p> : null}
              <div className="card-actions">
                {activity.status === "planned" ? (
                  <button
                    className="btn add-btn"
                    type="button"
                    disabled={busy}
                    onClick={markCompleted}
                  >
                    {t.markCompleted}
                  </button>
                ) : null}
                <button
                  className="btn-secondary"
                  type="button"
                  onClick={() =>
                    router.push(
                      `/farms/${params.id}/crops/${params.cropId}/activities/${params.activityId}/edit`,
                    )
                  }
                >
                  {t.edit}
                </button>
                <button className="btn-danger" type="button" onClick={onDelete}>
                  {t.deleteActivity}
                </button>
              </div>
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
