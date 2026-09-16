/**
 * Crop Details screen (auth-only): overview + calendar + activities timeline.
 * Display only — no advisory or recommendations.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "../../../../../components/AuthGate";
import { TimelineList } from "../../../../../components/ActivityTimeline";
import {
  observationStatusLabel,
  severityDot,
} from "../../../../../components/healthLabels";
import { seasonLabel, statusLabel } from "../../../../../components/cropLabels";
import {
  ApiError,
  api,
  getStoredToken,
  type Activity,
  type Crop,
  type Farm,
  type Fertilizer,
  type HealthObservation,
} from "../../../../../lib/api";
import { useAuth } from "../../../../../lib/auth";

export default function CropDetailsPage({
  params,
}: {
  params: { id: string; cropId: string };
}) {
  const { t } = useAuth();
  const router = useRouter();
  const [crop, setCrop] = useState<Crop | null>(null);
  const [farm, setFarm] = useState<Farm | null>(null);
  const [activities, setActivities] = useState<Activity[] | null>(null);
  const [fertilizers, setFertilizers] = useState<Fertilizer[] | null>(null);
  const [health, setHealth] = useState<HealthObservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const [c, f] = await Promise.all([
        api.getCrop(token, params.id, params.cropId),
        api.getFarm(token, params.id),
      ]);
      setCrop(c);
      setFarm(f);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
      return;
    }
    try {
      setActivities(
        await api.getTimeline(token, params.id, params.cropId).then((r) => r.activities),
      );
    } catch {
      setActivities([]); // timeline is auxiliary — details work without it
    }
    try {
      setFertilizers(await api.listFertilizers(token, params.id, params.cropId));
    } catch {
      setFertilizers([]); // fertilizer history is auxiliary too
    }
    try {
      setHealth(await api.listObservations(token, params.id, params.cropId));
    } catch {
      setHealth([]); // health records are auxiliary too
    }
  }, [params.id, params.cropId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onDelete() {
    if (!window.confirm(t.deleteCropConfirm)) return;
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.deleteCrop(token, params.id, params.cropId);
      router.push(`/farms/${params.id}/crops`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error");
    }
  }

  return (
    <AuthGate mode="auth">
      <main className="main">
        <p>
          <Link href={`/farms/${params.id}/crops`}>← {t.backToFarms}</Link>
        </p>
        {error ? <p className="form-error">{error}</p> : null}
        {!crop ? (
          <p className="muted">{t.loading}</p>
        ) : (
          <>
            <section className="hero">
              <h1>🌱 {crop.crop_name}</h1>
              <p>
                {crop.variety_name ?? ""} · {crop.area} {crop.area_unit} (
                {crop.area_in_acres} acre)
              </p>
            </section>

            <div className="grid">
              <div className="card">
                <h2>{t.basicInfo}</h2>
                <KV k={t.cropName} v={crop.crop_name} />
                <KV k={t.varietyLabel} v={crop.variety_name} t={t} />
                <KV k={t.area} v={`${crop.area} ${crop.area_unit}`} />
                <KV k={t.season} v={seasonLabel(t, crop.season)} />
                <KV k={t.statusLabel} v={statusLabel(t, crop.status)} />
              </div>

              <div className="card">
                <h2>{t.location}</h2>
                <KV k={t.farmName} v={farm?.farm_name} />
                <KV
                  k={t.villageLabel}
                  v={
                    farm
                      ? [farm.village, farm.taluka, farm.district]
                          .filter(Boolean)
                          .join(", ") || null
                      : null
                  }
                  t={t}
                />
                <KV k={t.sowingDate} v={crop.sowing_date} />
                <KV k={t.harvestDate} v={crop.expected_harvest_date} t={t} />
                {crop.notes ? <KV k={t.notes} v={crop.notes} /> : null}
                <div className="card-actions">
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() =>
                      router.push(`/farms/${params.id}/crops/${params.cropId}/edit`)
                    }
                  >
                    {t.edit}
                  </button>
                  <button className="btn-danger" type="button" onClick={onDelete}>
                    {t.deleteCrop}
                  </button>
                </div>
              </div>

              <div className="card">
                <h2>📅 {t.cropCalendar}</h2>
                <p>
                  <Link href={`/farms/${params.id}/crops/${params.cropId}/activities`}>
                    {t.cropCalendar} / {t.timeline} →
                  </Link>
                </p>
                <p>
                  <Link
                    href={`/farms/${params.id}/crops/${params.cropId}/activities/new`}
                  >
                    + {t.addActivity}
                  </Link>
                </p>
              </div>

              <div className="card">
                <h2>📸 {t.cropCheckTitle}</h2>
                <p className="muted">{t.cropCheckHint}</p>
                <p>
                  <Link href="/crop-check">{t.cropCheckTitle} →</Link>
                </p>
              </div>

              <div className="card">
                <h2>📝 {t.activities}</h2>
                {activities === null ? (
                  <p className="muted">{t.loading}</p>
                ) : (
                  <TimelineList
                    items={activities.slice(0, 5)}
                    t={t}
                    base={`/farms/${params.id}/crops/${params.cropId}/activities`}
                  />
                )}
              </div>

              <div className="card">
                <h2>🧪 {t.fertilizerHistory}</h2>
                {fertilizers === null ? (
                  <p className="muted">{t.loading}</p>
                ) : fertilizers.length === 0 ? (
                  <p className="muted">{t.noFertilizers}</p>
                ) : (
                  fertilizers.slice(0, 3).map((f) => (
                    <p key={f.id}>
                      <strong>{f.fertilizer_name}</strong> · {f.quantity}{" "}
                      {f.quantity_unit} · {f.application_date}{" "}
                      <Link
                        href={`/farms/${params.id}/crops/${params.cropId}/fertilizers/${f.id}`}
                      >
                        [{t.viewDetails}]
                      </Link>
                    </p>
                  ))
                )}
                <p>
                  <Link
                    href={`/farms/${params.id}/crops/${params.cropId}/fertilizers`}
                  >
                    {t.fertilizerHistory} →
                  </Link>
                  {" · "}
                  <Link
                    href={`/farms/${params.id}/crops/${params.cropId}/fertilizers/new`}
                  >
                    + {t.addFertilizer}
                  </Link>
                </p>
              </div>

              <div className="card">
                <h2>🐛 {t.healthTitle}</h2>
                <p className="muted">{t.healthHint}</p>
                {health === null ? (
                  <p className="muted">{t.loading}</p>
                ) : health.length === 0 ? (
                  <p className="muted">{t.noObservations}</p>
                ) : (
                  health.slice(0, 3).map((o) => (
                    <p key={o.id}>
                      <span>{severityDot(o.severity)}</span>{" "}
                      <strong>{displayHealthName(o)}</strong> · {o.observation_date} ·{" "}
                      {observationStatusLabel(t, o.status)}{" "}
                      <Link
                        href={`/farms/${params.id}/crops/${params.cropId}/health/${o.id}`}
                      >
                        [{t.viewDetails}]
                      </Link>
                    </p>
                  ))
                )}
                <p>
                  <Link href={`/farms/${params.id}/crops/${params.cropId}/health`}>
                    {t.healthTitle} →
                  </Link>
                  {" · "}
                  <Link
                    href={`/farms/${params.id}/crops/${params.cropId}/health/new`}
                  >
                    + {t.addObservation}
                  </Link>
                </p>
              </div>
            </div>
          </>
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

function displayHealthName(o: HealthObservation): string {
  return o.observed_name ?? o.pest_name ?? o.disease_name ?? o.observation_type;
}
